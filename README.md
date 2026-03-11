# mcp-serial-bridge

シリアル通信を介して外部デバイスを操作するための MCP(Model Context Protocol)サーバーです。
AI エージェントが `list_ports` / `connect` / `write_and_read` の 3 ツールを通じてシリアルポートを直接制御できます。

モデム、計測器、組み込みボード、レトロコンピュータなど、シリアルインタフェースを持つあらゆる機器を対象にできます。

## 前提

- **ローカル MCP サーバー**: このサーバーはユーザーのマシン上でローカルプロセスとして動作します。クラウドやリモートでの動作は想定していません。シリアルポートに物理的にアクセスできる PC 上で実行してください。
- **Visual Studio Code (VSCode) + GitHub Copilot**: MCP クライアントとして VSCode（GitHub Copilot Agent モード）を使用することを前提としています。他の MCP 対応クライアントからも利用できますが、本ドキュメントの手順は VSCode を基準に記載しています。

## 動作要件

- Python 3.11 以上
- macOS / Windows / Linux

## セットアップ

```bash
git clone https://github.com/46nori/mcp-serial-bridge.git
cd mcp-serial-bridge
```

### uv を使う場合（推奨）

```bash
# uv のインストール（未インストールの場合）
curl -LsSf https://astral.sh/uv/install.sh | sh

# 依存パッケージのインストールと仮想環境の作成
uv sync
```

### venv + pip を使う場合

uv が使えない環境では標準の venv も利用できます。

```bash
python3 -m venv .venv
.venv/bin/pip install "mcp[cli]>=1.9.0" "pyserial>=3.5"
```

> どちらの方法でも仮想環境は `.venv/` に作成されるため、VSCode の設定変更は不要です。

Linux でシリアルポートへのアクセス権がない場合は、ユーザーを `dialout` グループに追加してください。

```bash
sudo usermod -aG dialout $USER
# 反映には再ログインが必要
```

## サーバーの起動

`.vscode/mcp.json` はリポジトリに含まれているため、追加設定は不要です。
コマンドパレット（`Cmd+Shift+P` / `Ctrl+Shift+P`）から **MCP: Restart Server** を実行すると `serial-bridge` が利用可能になります。

設定ファイルの詳細は[技術詳細](#vscode-mcp-設定ファイル)を参照してください。

---

## 使用例

**ユーザーはツールを直接呼び出しません。** AI エージェント（GitHub Copilot）に自然言語で指示を出すと、AI が必要なツールを判断して順番に呼び出します。

```text
操作の流れ:
  ユーザー → 自然言語で指示 → AI エージェント → MCP ツール → シリアルデバイス
```

結果は AI の返答としてチャットに表示されます。

### 汎用 AT コマンド機器（モデム・Wi-Fi モジュールなど）

**ユーザーが AI に伝える内容:**
> 「シリアルポートを確認して、AT コマンドデバイスに 9600bps・改行コード CR+LF で接続し、AT コマンドで疎通確認と AT+GMR でバージョンを取得してください」

**AI が内部で呼び出すツールの引数（参考）:**

```json
{ "name": "list_ports", "arguments": {} }
{ "name": "connect",        "arguments": { "port": "/dev/cu.usbserial-10", "baudrate": 9600, "line_ending": "\r\n" } }
{ "name": "write_and_read", "arguments": { "command": "AT",     "wait_for": "OK", "timeout": 3 } }
{ "name": "write_and_read", "arguments": { "command": "AT+GMR", "wait_for": "OK", "timeout": 5 } }
```

---

### 計測器・センサー（CR のみ）

**ユーザーが AI に伝える内容:**
> 「COM3 に 115200bps で接続して（改行は CR のみ）、READ? コマンドで計測値を取得してください」

**AI が内部で呼び出すツールの引数（参考）:**

```json
{ "name": "connect",        "arguments": { "port": "COM3", "baudrate": 115200, "line_ending": "\r" } }
{ "name": "write_and_read", "arguments": { "command": "READ?", "wait_for": "\n", "timeout": 2 } }
```

---

### Linux/Raspberry Pi シリアルコンソール（LF のみ）

**ユーザーが AI に伝える内容:**
> 「/dev/ttyUSB0 に 115200bps で接続して（改行は LF のみ）、uname -a を実行してください」

**AI が内部で呼び出すツールの引数（参考）:**

```json
{ "name": "connect",        "arguments": { "port": "/dev/ttyUSB0", "baudrate": 115200, "line_ending": "\n" } }
{ "name": "write_and_read", "arguments": { "command": "uname -a", "wait_for": "$", "timeout": 5 } }
```

---

## 通信のモニタリング

本サーバーは MCP ローカルサーバーのため、**stdout は JSON-RPC プロトコル専用**です。
通信の観測には以下の3つの手段を使い分けます。

```text
┌────────────────────────────────────────────────────┐
│  AI エージェント (VSCode)                           │
│      ↕ stdout/stdin  (JSON-RPC 2.0専用)            │
│  mcp-serial-bridge                                  │
│      ├─ stderr  → VSCode Output パネル              │
│      ├─ logs/serial_YYYYMMDD.log  → 詳細ログ        │
│      └─ logs/rx_stream.log  → RX 生ストリーム       │
└────────────────────────────────────────────────────┘
```

### stderr — VSCode Output パネル

MCP サーバーの stderr は VSCode の **Output** パネル（`serial-bridge` チャンネル）に表示されます。
すべての送受信と接続イベントが方向付きで出力されます。

```log
[SYS] Connected to /dev/cu.usbserial-110 at 19200 baud
[TX] AT\r
[RX] AT\r\nOK\r\n
```

特徴: VSCode が付加するタイムスタンプが入るため、長い通信では見づらくなることがあります。

---

### `logs/serial_YYYYMMDD.log` — 詳細ログ

すべての TX / RX / SYS イベントをタイムスタンプ付きでファイルに記録します。
改行・制御文字はエスケープ済みのため、後から通信手順を正確に追跡できます。

```log
[2026-03-10T12:34:56.123] [SYS] Connected to /dev/cu.usbserial-110 at 19200 baud
[2026-03-10T12:34:57.001] [TX] AT\r
[2026-03-10T12:34:57.089] [RX] AT\r\nOK\r\n
```

用途: デバッグ・通信手順の記録など

---

### `logs/rx_stream.log` — RX 生ストリーム

デバイスから受信した生データのみをタイムスタンプなしでファイルに**追記**します。  
(データはUTF-8に変換されます)

**通信内容をリアルタイムに表示したい場合：**

```bash
touch logs/rx_stream.log
tail -f logs/rx_stream.log
```

**さらにファイルにキャプチャしたい場合:**

```bash
tail -f logs/rx_stream.log | tee logs/session_$(date +%H%M%S).log
```

用途: 純粋なシリアルモニタとして使う・機器の出力を記録する

## ツールリファレンス

### `list_ports`

現在接続されているシリアルポートの一覧を返します。
`connect` を呼ぶ前に必ず実行し、使用する `device` 名を確認してください。

> macOS では、カーネル内部用の `/dev/tty.*` は除外し、アプリ用の `/dev/cu.*` のみを返します。

**戻り値の例:**

```json
[
  {
    "device": "/dev/cu.usbserial-110",
    "description": "USB2.0-Serial",
    "hwid": "USB VID:PID=1A86:7523"
  }
]
```

---

### `connect`

指定したポートにシリアル接続します。すでに接続中の場合は安全に切断してから再接続します。

| 引数 | 型 | 既定値 | 説明 |
| --- | --- | --- | --- |
| `port` | string | 必須 | `list_ports` で取得した `device` 名 |
| `baudrate` | int | `19200` | 通信速度 (bps) |
| `line_ending` | string | `"\r"` | コマンド末尾に付加する改行コード |

**`line_ending` の選び方:**

| 値 | 意味 | 主な用途 |
| --- | --- | --- |
| `"\r"` | CR only（既定） | 組み込み機器・レガシーシリアル機器 |
| `"\r\n"` | CR+LF | Windows 系機器・一部のモデムや計測器 |
| `"\n"` | LF only | Linux/UNIX シェル・現代的な機器 |

接続後に変更する場合は `connect` を再実行してください（`write_and_read` に個別指定はできません）。

---

### `write_and_read`

コマンドを送信し、応答を受信して返します。事前に `connect` が必要です。

| 引数 | 型 | 既定値 | 説明 |
| --- | --- | --- | --- |
| `command` | string | 必須 | 送信するコマンド文字列 |
| `wait_for` | string | `""` | この文字列が受信に現れるまで待機 |
| `timeout` | float | `5.0` | 最大待機時間（秒） |

- `wait_for` を省略した場合、データの受信が途切れた時点で即座に返ります。
- プロンプト文字列（例: `"> "`, `"OK"`, `"#"`）を指定することで、機器が応答し終わるまで正確に待機できます。
- 送信前に受信バッファをクリアするため、前コマンドの残データが混入しません。

---

## 技術詳細

### VSCode MCP 設定ファイル

`.vscode/mcp.json` はリポジトリに含まれており、VSCode が自動で読み込みます。`${workspaceFolder}` 変数は VSCode が実行時に展開するため、手動での編集は不要です。

```json
{
  "servers": {
    "serial-bridge": {
      "type": "stdio",
      "command": "${workspaceFolder}/.venv/bin/python",
      "args": ["${workspaceFolder}/src/server.py"]
    }
  }
}
```

> **Windows ユーザーへ**: Python の実行ファイルは `.venv\Scripts\python.exe` にあるため、`command` を `"${workspaceFolder}/.venv/Scripts/python.exe"` に変更してください。

### MCP プロトコル

AI とサーバー間は **MCP (JSON-RPC 2.0) over stdio** で通信します。たとえば `connect` の呼び出しは以下のような JSON になります。ユーザーがこの JSON を書く必要はありません。

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/call",
  "params": {
    "name": "connect",
    "arguments": {
      "port": "/dev/cu.usbserial-10",
      "baudrate": 9600,
      "line_ending": "\r\n"
    }
  }
}
```

### 他の MCP 対応クライアントから使用する

`type: stdio` に対応した任意の MCP クライアントから利用できます。VSCode の `${workspaceFolder}` 変数は使えないため、**絶対パス**で指定してください。

**Claude Desktop の例** (`~/Library/Application Support/Claude/claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "serial-bridge": {
      "command": "/Users/yourname/mcp-serial-bridge/.venv/bin/python",
      "args": ["/Users/yourname/mcp-serial-bridge/src/server.py"]
    }
  }
}
```

| クライアント | 設定ファイルのパス |
| --- | --- |
| **Claude Desktop** (macOS) | `~/Library/Application Support/Claude/claude_desktop_config.json` |
| **Claude Desktop** (Windows) | `%APPDATA%\Claude\claude_desktop_config.json` |
| **Cursor** | `.cursor/mcp.json` またはグローバルの `~/.cursor/mcp.json` |
