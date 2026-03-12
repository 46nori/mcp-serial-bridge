# サンプル

## Zorkの自律攻略

Z80のCP/Mマシン[Z80ATmega](https://github.com/46nori/Z80Atmega128)にシリアル接続し、このMCPサーバー経由でCP/Mを遠隔操作する。
CP/M 2.2上で動作する、[Zork I](https://ja.wikipedia.org/wiki/%E3%82%BE%E3%83%BC%E3%82%AF)というテキストアドベンチャーゲームを、AIエージェントに攻略させる。

使用するのは、VSCode(Visual Source Code)上で動作する、GitHub CopilotのAIエージェント

### 実行方法

1. VSCodeを起動
2. MCPサーバーの起動
   1. コマンドパレットで `MCP: List Server` を選択
   2. `serial-bridge`を選択
   3. `サーバーの起動`または`サーバーの再起動`
3. シリアル通信をモニタするための設定
   1. ターミナルを開く
   2. `logs/`に移動
   3. `rx_stream.log` を `tail -f` でリアルタイム表示する。(`log.txt`にロギングも行っている)

        ```bash
        rm rx_stream.log; touch rx_stream.log; tail -f rx_stream.log | tee log.txt
        ```

4. Copilotのチャットを起動
   1. Copilotチャットを開く
   2. Agentモードにする
   3. LLMモデルを選択
   4. プロンプトでゲーム攻略を指示

        ```text
        #file:prompt_zork1.md を読んで、ゲームの攻略を開始してください。
        ```

5. 攻略の様子を見守る。指示を求められたら適宜対応。

### 攻略の様子

LLMモデルはGPT-5.4を使用している。

[チャット](./log_chat.txt)

[コンソールのキャプチャ](./log_zork1.txt)

[![Zork攻略](https://img.youtube.com/vi/9ECWXsUKDJA/hqdefault.jpg)](https://youtu.be/9ECWXsUKDJA)
