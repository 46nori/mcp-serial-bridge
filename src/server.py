"""
mcp-serial-bridge: シリアル通信を介して外部デバイスを操作するMCPサーバー
"""

import platform
import sys
import time
from datetime import datetime
from pathlib import Path

import serial
import serial.tools.list_ports
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("mcp-serial-bridge")

# グローバルなシリアル接続状態
_serial: serial.Serial | None = None
_connected_port: str | None = None
_line_ending: str = "\r"  # connect で変更可能

LOGS_DIR = Path(__file__).parent.parent / "logs"
LOGS_DIR.mkdir(exist_ok=True)

# RX 生データのみを書き出すストリームファイル（tail -f でモニタ可能）
RX_STREAM_FILE = LOGS_DIR / "rx_stream.log"


def _get_log_file() -> Path:
    today = datetime.now().strftime("%Y%m%d")
    return LOGS_DIR / f"serial_{today}.log"

def _log(direction: str, data: str) -> None:
    """
    ログファイルへの追記と RXストリームファイルへの生データ書き出しを行う。
    """
    # ログファイル: タイムスタンプ, 方向, エスケープ済みデータを出力
    timestamp = datetime.now().isoformat(timespec="milliseconds")
    escaped = data.replace("\r", "\\r").replace("\n", "\\n")
    with _get_log_file().open("a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] [{direction}] {escaped}\n")

    # RXストリームファイル: 生データのみ追記
    if direction == "RX":
        with RX_STREAM_FILE.open("a", encoding="utf-8") as f:
            f.write(data)

    # stderr: MCP Output パネルに方向付きで出力
    sys.stderr.write(f"[{direction}] {escaped}\n")
    sys.stderr.flush()

@mcp.tool()
def list_ports() -> list[dict]:
    """
    接続されているすべてのシリアルポートの情報を返す。
    connect の呼び出し前に必ず実行し、利用可能なポート(device名)を確認すること。
    macOSでは /dev/cu.* を優先的に返す（/dev/tty.* はカーネル内部用のため除外）。

    Returns:
        list of dict with keys:
          - device: OS固有の識別子 (例: COM3, /dev/cu.usbserial-10)
          - description: デバイス名
          - hwid: ハードウェアID (VID:PID)
    """
    ports = serial.tools.list_ports.comports()

    result = [
        {
            "device": p.device,
            "description": p.description or "",
            "hwid": p.hwid or "",
        }
        for p in ports
    ]

    # macOS: /dev/tty.* は除外して /dev/cu.* のみを返す
    if platform.system() == "Darwin":
        result = [
            p for p in result if not p["device"].startswith("/dev/tty.")
        ]

    return result

@mcp.tool()
def connect(port: str, baudrate: int = 19200, line_ending: str = "\r") -> str:
    """
    指定したシリアルポートに接続する。
    port には list_ports で取得した device 名を指定する。
    すでに接続中の場合は、内部で既存接続を閉じてから再接続する。

    Args:
        port: 接続ポート名 (例: /dev/cu.usbserial-10, COM3)
        baudrate: 通信速度 (default: 19200)
        line_ending: コマンド末尾に付加する改行コード
            "\r"   (CR only, default)
            "\r\n" (CR+LF)
            "\n"   (LF only)
    """
    global _serial, _connected_port, _line_ending

    # 既存接続を閉じる
    if _serial is not None and _serial.is_open:
        _log("SYS", f"Closing existing connection to {_connected_port}")
        _serial.close()
        _serial = None
        _connected_port = None

    try:
        _serial = serial.Serial(port, baudrate=baudrate, timeout=0.1)
        _connected_port = port
        _line_ending = line_ending
        _log("SYS", f"Connected to {port} at {baudrate} baud, line_ending={line_ending!r}")
        return f"Connected to {port} at {baudrate} baud (line_ending={line_ending!r})."

    except serial.SerialException as e:
        err_msg = str(e)
        if "Permission denied" in err_msg:
            hint = (
                " ユーザーを dialout グループに追加してください: sudo usermod -aG dialout $USER"
                if platform.system() == "Linux"
                else ""
            )
            raise RuntimeError(
                f"ポート {port} へのアクセスが拒否されました。{hint}"
            ) from e
        if "Resource busy" in err_msg or "Errno 16" in err_msg:
            raise RuntimeError(
                f"ポート {port} は別のプロセスが使用中です。"
                " 他の mcp-serial-bridge インスタンスや別のシリアルターミナルが接続していないか確認してください。"
            ) from e
        # Windows: ポート使用中・権限不足は同じエラーメッセージになる
        if platform.system() == "Windows" and ("Access is denied" in err_msg or "Error 5" in err_msg):
            raise RuntimeError(
                f"ポート {port} へのアクセスが拒否されました。"
                " ポートが他のアプリに使用中でないか確認してください。解決しない場合は管理者権限で実行してください。"
            ) from e
        raise RuntimeError(f"接続エラー: {err_msg}") from e

@mcp.tool()
def write_and_read(
    command: str,
    wait_for: str = "",
    timeout: float = 5.0,
) -> str:
    """
    シリアルポートにコマンドを送信し、応答を受信して返す。
    事前に connect を実行しておくこと。
    行末には connect で設定した line_ending が自動付加される。
    wait_for にプロンプト文字列（例: "> "）を指定すると、
    その文字列が受信データに現れるまで待機する。
    送受信データはすべてログファイルに記録される。

    Args:
        command: 送信する文字列
        wait_for: この文字列が出現するまで受信を待機する（省略可）
        timeout: 最大待機時間（秒）
    """
    global _serial

    if _serial is None or not _serial.is_open:
        raise RuntimeError(
            "シリアルポートに接続されていません。先に connect を実行してください。"
        )

    # 送信前に受信バッファをクリア（前コマンドの残データを捨てる）
    _serial.reset_input_buffer()

    # 送信（connect で設定した line_ending を付加）
    tx_data = command.rstrip("\r\n") + _line_ending
    _serial.write(tx_data.encode("utf-8"))
    _log("TX", tx_data)

    # デバイスがコマンドを処理し始めるまで少し待つ
    time.sleep(0.1)

    # 受信: ポーリング
    received = ""
    deadline = time.monotonic() + timeout

    while time.monotonic() < deadline:
        if _serial.in_waiting > 0:
            chunk = _serial.read(_serial.in_waiting)
            decoded = chunk.decode("utf-8", errors="replace")
            received += decoded
            _log("RX", decoded)

            if wait_for and wait_for in received:
                break
        else:
            # wait_for 未指定かつデータをすでに受信済みなら終了
            if not wait_for and received:
                break
            time.sleep(0.05)

    return received

if __name__ == "__main__":
    mcp.run()
