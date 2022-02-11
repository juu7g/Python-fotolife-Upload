"""
はてなフォトライフに画像をアップロードする
"""

from base64 import b64encode
from hashlib import sha1
from typing import Tuple
import sys, os, secrets
from datetime import datetime
import requests
import xml.etree.ElementTree as ET
import tkinter as tk
from tkinter import filedialog

class HatenaFotolifeAtom():
    """
    はてなフォトライフへアクセスするためのAtomクラス
    """

    def get_image_url_et(self, xml:str) -> Tuple[str, str]:
        """
        xmlからETのiterで情報を取得

        Args:
            str:        xml
        Returns:
            str, str:   画像url、画像foto記法
        """
        root = ET.fromstring(xml)
        url1 = next(root.iter("{http://www.hatena.ne.jp/info/xmlns#}imageurl")).text
        url2 = next(root.iter("{http://www.hatena.ne.jp/info/xmlns#}syntax")).text
        return url1, url2
        
    def get_image_url_et_find(self, xml:str) -> Tuple[str, str]:
        """
        xmlからETのfindで情報を取得
        iterより少し遅い

        Args:
            str:        xml
        Returns:
            str, str:   画像url、画像foto記法
        """
        ns = {'hatena': 'http://www.hatena.ne.jp/info/xmlns#'}

        root = ET.fromstring(xml)
        url1 = root.find("hatena:imageurl", ns).text
        url2 = root.find("hatena:syntax", ns).text
        return url1, url2
        
    def get_image_url_bs4(self, xml:str) -> Tuple[str, str]:
        """
        xmlからBeautifulSoupで情報を取得
        単純なxmlだからかETに比べて遅い

        Args:
            str:        xml
        Returns:
            str, str:   画像url、画像foto記法
        """
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(xml, "html.parser")
        url1 = soup.find("hatena:imageurl").get_text()
        url2 = soup.find("hatena:syntax").get_text()
        return url1, url2


    def wsse(self, username: str, api_key: str) ->str:
        """
        WSSE認証

        Args:
            str:        はてなフォトライフのユーザーID
            str:        はてなブログのapi key
        Returns:
            str:        送信用認証WSSEデータ
        """
        # 安全なnonceの生成
        # token_urlsafe()で生成してBase64でエンコードしたが長さは4の倍数でないとデコードできない
        # "="を付加して長さを調整する方法もあるようだがエンコードできるか心配なのでバイト型で作成してエンコードする
        # nonce64 = secrets.token_urlsafe(16)  
        nonce = secrets.token_bytes()                   # 安全な乱数発生
        nonce64 = b64encode(nonce).decode()             # b64encodeはバイト型のため文字型に変換
        created = datetime.utcnow().isoformat() + "Z"   # UTC(協定世界時)でiso表記

        # PasswordDigest：Nonce, Created, APIキーを文字列連結し、SHA1アルゴリズムでダイジェスト化
        # 更にBase64エンコード
        password_digest = nonce + created.encode() + api_key.encode()    # sha1の入力はバイト型のため
        password_digest = sha1(password_digest).digest()
        password_digest = b64encode(password_digest).decode()

        # WSSE認証文字列作成
        s = f'UsernameToken Username="{username}", PasswordDigest="{password_digest}", Nonce="{nonce64}", Created="{created}"'
        return s

    def create_data(self, file_name:str, title:str="", folder:str="Hatena Blog") ->str:
        """
        送信画像データの作成

        Args:
            str:        画像のパス
            str:        はてなフォトライフ上で画像につけるタイトル
            str:        はてなフォトライフのフォルダ
        Returns:
            str:        送信用xmlデータ
        """
        with open(file_name, "rb") as image_file:
            uploadData = image_file.read()
        uploadData = b64encode(uploadData).decode()
        extension_ = os.path.splitext(file_name)[1][1:].lower()      # 拡張子のみ取得
        if extension_ == "jpg": extension_ = "jpeg"
        xml_data = f"""<entry xmlns="http://purl.org/atom/ns#">
        <title>{title}</title>
        <content mode="base64" type="image/{extension_}">{uploadData}</content>
        <dc:subject>{folder}</dc:subject>
        </entry>"""
        return xml_data

    def post_hatena(self, data:str) ->Tuple[str, str]:
        """
        画像アップロード

        Args:
            str:        送信データ
        Returns:
            str, str:   画像url、画像foto記法
        """
        headers = {'X-WSSE': self.wsse(os.getenv("py_hatena_username"), os.getenv("py_hatena_api_key"))}
        endpoint = 'https://f.hatena.ne.jp/atom/post/'
        
        # postのdataに日本語が含まれる場合、エンコードが必要
        r = requests.post(endpoint, data=data.encode("utf-8"), headers=headers)

        print(f'--result-- status code={r.status_code}')
        if r.status_code != 201:
            sys.stderr.write(f'Error!\nstatus_code: {r.status_code}\nmessage: {r.text}')
            return "", ""
        try:
            r.raise_for_status()
            url1, url2 = self.get_image_url_et(r.text)
            print(f'url  : {url1}')
            print(f'foto : {url2}')
        except:
            sys.stderr.write(f'Error!\nstatus_code: {r.status_code}\nmessage: {r.text}')
        if url1:
            return url1, url2
        else:
            return "", ""
        
    def log_output(self, image_path:str, folder:str, image_url:str, foto:str):
        """
        ログ出力 ファイルはカレントディレクトリに「fotolife_yymmdd.log」
                追加型書き込み
                コピペでmarkdows記法で使用できるように編集して出力
        Args:
            str:        画像ファイルパス
            str:        フォルダ名
            str:        画像url
            str:        画像foto記法
        """
        foto = foto.replace(":image", ":plain")
        logfile_name = f"fotolife_{datetime.now().strftime('%y%m%d')}.log"
        upload_time = f"Time:{datetime.now().strftime('%Y-%m-%d %H:%M')}"
        msg = f"\n【{os.path.basename(image_path)}】Folder:{folder} {upload_time}\n url  : ![]({image_url}) \n foto : [{foto}] \n"
        try:
            with open(logfile_name, mode="a") as file_:
                file_.write(msg)
        except Exception as e:
            print(f"書き込みエラー：{e}")

def upload_image_to_hatena():
    """
    画像をはてなフォトライフへアップロードする
    はてなフォトライフのアップロード先フォルダを入力して指定する
    画像はコマンドライン引数、基本はドラッグアンドドロップ
    """
    hatena_atom = HatenaFotolifeAtom()
    exp = (".png", ".jpg", ".jpeg", ".gif")     # 対象の拡張子
    kwargs = {}

    # コマンドライン引数からドラッグ＆ドロップされたファイル情報を取得
    if len(sys.argv) > 1:
        file_paths = tuple(sys.argv[1:])
    else:
        # 画像を指定
        root = tk.Tk()      # 自動で作成されるToplevelオブジェクトを手動で作成し
        root.withdraw()     # 撤去状態にする
        file_paths = filedialog.askopenfilenames(
            filetypes=[("画像", ".png .jpg .jpeg .gif"), ("PNG", ".png"), ("JPEG", ".jpg .jpeg"), ("GIF", ".gif"), ("すべて", "*")])

    # アップロード先フォルダを入力
    folder = input("はてなフォトライフのフォルダ名を指定してください(無指定の場合は「Hatena Blog」)\n>")
    if not folder:
        folder = "Hatena Blog"
    kwargs["folder"] = folder

    # ファイルごとにアップロード
    for file_ in file_paths:
        if not os.path.splitext(file_)[1].lower() in exp:
            print(f"File : {os.path.basename(file_)}は対象外のファイルです。")
            continue

        title_ = os.path.splitext(os.path.basename(file_))[0]       # ローカルファイル名をタイトルに
        data = hatena_atom.create_data(file_, title_, **kwargs)     # 送信データ作成
        print(f"【{os.path.basename(file_)}】")
        image_url, foto = hatena_atom.post_hatena(data)             # 送信と結果取得
        hatena_atom.log_output(file_, folder, image_url, foto)              # ログ出力
    input("\n確認したらEnterキーを押してください")

def test_parse_xml():
    """
    はてなフォトライフへ画像をアップロードした時に返ってくるxmlの解析テスト
    処理時間を出力
    """
    import time
    path = r'C:\temp\result_text.xml'
    with open(path, mode="r") as f:
        xml = f.read()
    hatena_atom = HatenaFotolifeAtom()
    funcs = [hatena_atom.get_image_url_et, hatena_atom.get_image_url_bs4, hatena_atom.get_image_url_et_find]
    for func in funcs:
        t1 = time.time()
        print(f"\n*** test by {func.__name__}")
        url1, url2 = func(xml)
        t2 = time.time()
        print(f'url        : {url1}')
        print(f'url foto   : {url2}')
        print(f"*** time:{t2 - t1}")
    # print(f"ET  time:{t2 - t1}")
    # print(f"ETf time:{t4 - t3}")
    # print(f"bs4 time:{t3 - t2}")


if __name__ == '__main__':
    upload_image_to_hatena()
    # test_parse_xml()