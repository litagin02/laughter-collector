# Laughter Collector

音声データから笑い声を抽出してデータセットを作成するためのスクリプト群です。また非言語音声や感嘆詞の抽出も可能です（が誤りが多いかもしれません）。

## 原理

- 音声ファイルを読み込み、-40dBを無音とみなしスライス
- スライスした音声データに対して、Whisperで書き起こしを行う
- 書き起こしデータに対して、正規表現を用いて笑い声かどうか・非言語音声や感嘆詞かどうかを判定

## 使い方

Python>=3.10とNVidia GPUが必要です。

### インストール

```bash
git clone https://github.com/litagin02/laughter-collector
cd laughter-collector
python -m venv venv
venv\Scripts\activate
pip3 install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
pip install -r requirements.txt
```

### 元データの準備

- 音声ファイルたちをディレクトリ（以下`path/to/original_data`とする）に格納
- 各ファイルの拡張子は".wav", ".mp3", ".flac", ".ogg", ".opus"のいずれかである必要があります（必要に応じて`utils.py`を書き換えれば他もいけます）。
- `path/to/original_data`では好きなようにサブディレクトリたちの階層を作ってそこに音声ファイルを格納してください。**デフォルトでは直下の音声ファイルは反映されず、1つ下の階層からのみ反映されます**。直下のみを反映するには`-nr`オプションを指定してください。
- 結果は相対パスを保持したまま指定した`path/to/output`に保存されます。

### データセットの作成

```bash
python collect_laughter.py -i path/to/original_data -o path/to/output
```

裏では`splice.py`が呼び出され、マルチプロセスで音声を切り出して`path/to/output/temp`にスライスされた音声が保存されて行き、それを本体のスクリプトが順次読み込んで書き起こしをバッチ処理で行います。

細かい他の引数はコードを参照してください。

### 結果

元々の音声ファイルが以下のような構造だったとします。
```
path/to/original_data
├── subdir1
│   ├── foo.wav
│   ├── bar.mp3
│   └── baz.ogg
└── subdir2
    ├── subdir3
    │   └── qux.mp3
    └── quux.flac
```

結果は以下のような構造になります。
```
path/to/output
├── laugh
│   ├── subdir1
│   |   ├── laugh.csv
│   │   ├── foo_0.wav
│   │   ├── foo_1.wav
│   │   ├── bar_0.wav
│   │   └── baz_0.wav
│   └── subdir2
│       ├── subdir3
│       |   ├── laugh.csv
│       │   └── qux_0.wav
|       ├── laugh.csv
│       └── quux_0.wav
├── nv
│   ├── subdir1
│   |   ├── nv.csv
│   │   ├── foo_2.wav
| ...
└── trans
    ├── subdir1
    │   └── all.csv
    └── subdir2
        ├── subdir3
        │   └── all.csv
        └── all.csv
```

ここで`foo_0.wav`は`foo.wav`の0番目のスライスを示しています。`trans.csv`は書き起こしデータです。また`laugh.csv`は笑い声と判定されたスライスの書き起こし、`nv.csv`は非言語音声や感嘆詞と判定されたスライスの書き起こし、また`all.csv`はそれ以外も含めた全てのスライスの書き起こしです。

### 注意

- 笑い声の判定と非言語音声の判定では笑い声が優先されます。
- 笑い声や非言語音声の判定の正規表現は改良の余地があると思うので、必要に応じて`pattern.py`を変更してください。
- 非言語音声の判定は誤りが多く、特定のひらがなから単語ができてしまう場合それが非言語音声として判定されることがあります。結果を見ながら、そのような単語を`exclude_words.txt`に追加してください（毎回このファイルが参照されるので、スクリプト実行中でも変更が反映されます）。
- スライスの細かいパラメータや、笑い声正規表現等は、それぞれ`splice.py`、`pattern.py`内を参照しつつ必要ならば変更してください。
- デフォルトでは笑い声等判定のための書き起こしにはHugging FaceのWhisperのmediumモデルが使われます（笑い声や非言語音声かどうかさえ判定できればよく書き起こし精度はそこまで必要がない）、が必要に応じて`collect_laughter.py`の引数`--model large-v2`等でモデルを指定できます。
- 細かい他の引数等はコードを参照してください。

## その他のスクリプト

結果の笑い声ファイルたちに対するFaster Whisper (large-v2) での書き起こし：
```bash
python transcribe.py -i path/to/output/laugh -o transcriptions.csv
```
