"""
短いセリフが「笑い声か」「感嘆詞・非言語音声か」を判定するための正規表現を提供するモジュール。
is_laughing()とis_nv()関数を提供する。
"""

import re
import jaconv
import pyopenjtalk
import unicodedata
from pathlib import Path
import shutil

"""
非言語音声・感嘆詞等ではないのにマッチしてしまう単語を除外するためのファイル。
結果を見ながら随時exclude_words.txtに追加してください。
"""
exclude_words_file = Path("exclude_words.txt")
if not exclude_words_file.exists():
    shutil.copy("exclude_words_default.txt", "exclude_words.txt")

punctuations = re.escape("。、.,!?！？")


def normalize_text(text: str) -> str:
    """
    日本語文章を句読点や空白等を排除し正規化する。
    ひらがな、カタカナ、漢字、アルファベット、数字、句読点等以外の文字を削除する。
    長音符や「っ」や句読点等の連続を1つにする。「…」→「.」に注意。
    句読点は正規化されて「。」「、」「.」「!」「?」になる。
    """
    text = unicodedata.normalize("NFKC", text)
    # この段階で「…」は「...」に変換されることに注意

    text = text.replace("~", "ー")
    text = text.replace("～", "ー")
    text = text.replace("〜", "ー")
    text = text.replace("・", ".")

    text = re.sub(
        # ↓ ひらがな、カタカナ、漢字
        r"[^\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF\u3400-\u4DBF\u3005"
        # ↓ 半角アルファベット（大文字と小文字）
        + r"\u0041-\u005A\u0061-\u007A"
        # ↓ 半角数字
        + r"\u0030-\u0039"
        # ↓ 句読点等
        + punctuations
        # 上述以外の文字を削除
        + r"]+",
        "",
        text,
    )
    text = text.replace("\u3099", "")  # 結合文字の濁点を削除、る゙ → る
    text = text.replace("\u309A", "")  # 結合文字の半濁点を削除、な゚ → な

    # 「ー」の連続を1つにする
    text = re.sub(r"ー+", "ー", text)
    # punctuationsと「ー」と「っ」と「ッ」の連続を1つにする
    text = re.sub(rf"([{punctuations}ーっッ])\1+", r"\1", text)
    return text


# 「ー」と「っ」を取り除いた文章に対するひらがなの笑い声の正規表現
warai_pattern = (
    r"(("
    + r"(ん|む)*"
    # 「は」行を最後に含む系統
    + r"(あ+|い+|う+|え+|お+)(は+|ひ+|ふ+|へ+|ほ+)|"
    + r"かは+|きひ+|く(は+|ひ+|ふ+|へ+|ほ+)|けへ+|"
    + r"がは+|ぎひ+|ぐ(は+|ひ+|ふ+|へ+|ほ+)|げへ+|"
    + r"きゃは+|ぎゃは+|"
    + r"たは+|てへ+|"
    + r"なは+|に(は+|ひ+|ふ+|へ+|ほ+)|ぬ(は+|ひ+|ふ+|へ+|ほ+)|"
    + r"にゃは+|にゅふ+|にょほ+|"
    + r"ふ+(は+|ひ+|ふ+|へ+|ほ+)|"
    + r"ぶ+(は+|ひ+|ふ+|へ+|ほ+)|"
    + r"ぷ+(は+|ひ+|ふ+|へ+|ほ+)|"
    + r"(む|も)(は+|ひ+|ふ+|へ+|ほ+)|"
    + r"わ+は+|うぃひ+|うぇへ+|うぉほ+|"
    + r"ん(は+|ひ+|ふ+|へ+|ほ+)|"
    # 「ひゃ」で終わる系統（叫び声もある）
    + r"あ(ひゃ)+|う(ひゃ)+|う(ひょ)+|"
    # 「し」で終わる系統
    + r"(い|き|に)し+|"
    # 「ん」で終わる系統（自慢げや感心の感嘆詞の可能性もある）
    + r"ふ{2,}ん|へ{2,}ん|ほ{2,}ん|"
    # 2回以上の繰り返し
    + r"か{2,}|く{2,}|け{2,}|は{2,}|ひ{2,}|ふ{2,}|へ{2,}|ほ{2,}|ぷ{2,}|"
    # 擬態語
    + r"くす|けら|げら|にこ|にや|にた|にか|にま|"
    + r"てへ+|"
    + r"にやり)ん*)+"
)

# 母音撥音促音等のパターン
basis = r"[あいうえおやゆよわんぁぃぅぇぉゃゅょゎーっ]"


# (母音 +)◯◯(+ 母音)で感嘆詞とみなせるパターン
single_nv_pattern = (
    # フィラー
    r"あ[あー]+|あの[うおー]*|え[ーっ]*と?|その[おー]*|ま[あー]+|う[ー]*ん?|"
    # それ以外の単体の感嘆詞や口語表現
    + r"ちぇ|くそ|(やれ){2,}|すご|ち(き|く)しょ|やば|まじで?っ*す?か?|あれ+|でし|"
    + r"おっ?け|あっぱれ|おっ?す|うぃ?っ?す|しまった|よくも?|"
)

# ひらがな（「ー」「っ」含む）に対する非言語音声・感嘆詞の正規表現
nv_pattern = (
    r"("
    # 母音等の2回以上の繰り返しの場合（「うおわー」「いやぁ」「うん」等）
    + rf"{basis}{{2,}}|"
    # 母音等以外が先頭・間に来る場合（「やったー」「げげ」「ぎょわあーーっ」「うみゃみゃーん」等）
    + rf"{basis}*("
    # このブロックの中は単体文字でヒットするので、
    # これらの文字（と母音等）からできる単語が含まれてしまうことに注意
    # このためexclude_wordsで手動でそのようなものを除外する
    + r"き+|く+|が+|ぎ+|ぐ+|げ+|し+|そ+|た+|て+|と+|だ+|ど+|な+|に+|ぬ+|は+|ひ+|ふ+|へ+|ほ+|む+|"
    + r"ち?(ちゃ)+|ち?(ちゅ)+|ち?(ちょ)+|(でゅ)+|に?(にゃ)+|み?(みゃ)+|(ひゃ)+|(ひゅ)+|(ひょ)+|(しゃ)+|(しゅ)+|(しょ)+|"
    + rf"{single_nv_pattern}"
    + rf"){basis}*|"
    # 「ら」「りゃ」が間に入る場合（「ありゃ」「おらー」「てりゃりゃー」等）
    + rf"[あいうおこてとんぁぃぅぇぉゃゅょゎーっ]+(ら|りゃ)+{basis}*"
    + r")+"
)


def is_laughing(norm_text: str) -> bool:
    # punctuationsを削除
    norm_text = re.sub("[" + punctuations + "]", "", norm_text)
    # wの繰り返しの場合はTrueを返す（書き起こし結果がたまに「www」となる）
    if re.fullmatch(r"(w|W)+", norm_text):
        return True
    # ひらがな、カタカナ以外があったらFalseを返す
    if not re.fullmatch(r"[\u3040-\u309F\u30A0-\u30FF]+", norm_text):
        return False
    # カタカナをひらがなに変換
    norm_text = jaconv.kata2hira(norm_text)
    # 「ー」と「っ」を取り除く
    norm_text = re.sub("[っー]", "", norm_text)

    # カタストロフバックトラッキングを防ぐために、は行の3回以上の繰り返しを2回にする
    norm_text = re.sub(rf"([は|ひ|ふ|へ|ほ])\1{{3,}}", r"\1\1", norm_text)
    # 全体がパターンにマッチするかどうかを判定
    return bool(re.fullmatch(warai_pattern, norm_text))


def is_kandoushi(text: str) -> bool:
    result = pyopenjtalk.run_frontend(text)
    pos_set = set(r["pos"] for r in result)
    if not pos_set.issubset({"感動詞", "フィラー", "記号"}):
        return False
    if pos_set == {"記号"}:
        return False
    return True


def is_nv(norm_text: str) -> bool:
    if norm_text == "":
        return False
    # 漢字・アルファベット・数字が含まれていたらFalseを返す
    if bool(
        re.search(
            r"[\u4E00-\u9FFF\u3400-\u4DBF\u0041-\u005A\u0061-\u007A\u0030-\u0039]",
            norm_text,
        )
    ):
        return False

    # 句読点のみからなればTrueを返す
    if re.fullmatch("[" + punctuations + "]+", norm_text):
        return True

    # 解析で感動詞、フィラー、記号のみからなればTrueを返す
    if is_kandoushi(norm_text):
        return True

    # 句読点を削除（「ー」「っ」は残す）
    norm_text = re.sub("[" + punctuations + "]", "", norm_text)
    # ここまででtextはひらがな、カタカナのみからなる

    # カタカナをひらがなに変換
    norm_text = jaconv.kata2hira(norm_text)

    # カタストロフバックトラッキングを防ぐために、母音等の3回以上の繰り返しを2回にする
    norm_text = re.sub(rf"({basis})\1{{3,}}", r"\1\1", norm_text)

    # カタストロフバックトラッキングを防ぐために、10文字で切る
    norm_text = norm_text[:10]
    # nvパターンにマッチするかどうかを判定
    if not bool(re.fullmatch(nv_pattern, norm_text)):
        return False

    # 特定の単語が含まれている場合はFalseを返す
    # 主に上のパターンでの1文字部分の繰り返しで意味のある単語ができてしまう場合に使用
    with exclude_words_file.open("r", encoding="utf-8") as f:
        exclude_words = f.read().splitlines()

    if any(word in norm_text for word in exclude_words):
        return False

    return True
