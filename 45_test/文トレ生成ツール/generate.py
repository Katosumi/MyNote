import os
import json
import ssl
import urllib.request
import datetime

# --- 設定 ---
# 取得したNotion APIトークン
NOTION_TOKEN = "NOTION_TOKEN_REMOVED"
# ArchiveページのID
ARCHIVE_PAGE_ID = "c39708cb56ba43918718f8515e4964d7"
# 抽出したテキストファイルのパス（スクリプトと同じフォルダにある前提）
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ARCHIVE_TEXT_PATH = os.path.join(BASE_DIR, "archive_text.txt")

def get_gemini_key():
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        print("💡 初回起動：Google GeminiのAPIキー（無料）が必要です。")
        print("取得先: https://aistudio.google.com/app/apikey （Googleアカウントでログインして作成）")
        key = input("👉 取得したGemini APIキーをペーストしてください: ").strip()
        
        # 次回から入力しなくて済むよう、Mac(.zshrc等)に設定することをおすすめするメッセージ
        print("\n※毎回入力が面倒な場合は、ターミナルで以下を実行して環境変数に設定してください。")
        print(f"  echo 'export GEMINI_API_KEY=\"{key}\"' >> ~/.zshrc && source ~/.zshrc\n")
    return key

def generate_text(theme, content, api_key):
    print("\n🧠 Geminiがあなたの文体で執筆中...（数秒〜十数秒かかります）")
    # 安価＆高速な flash モデルを使用
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
    
    try:
        with open(ARCHIVE_TEXT_PATH, "r", encoding="utf-8") as f:
            archive_data = f.read()
            # コンテキスト文字数上限を守るため、安全に先頭テキストを抽出
            archive_data = archive_data[:30000] 
    except Exception as e:
        print(f"❌ 過去の文章データ({ARCHIVE_TEXT_PATH})の読み込みに失敗しました: {e}")
        return None

    system_prompt = f"""
あなたは私の「文章執筆アシスタント」です。
以下の【過去の文章データ（Archive）】を深く読み込み、私の「文体、言葉遣い、思考の癖、リズム」を完全に模倣して、指定された【テーマ】と【内容】で新しい文章を作成してください。

【厳守するルール】
1. タイトル（要約）は、10〜12文字で作成すること。
2. 本文は、680〜700文字で作成すること。
3. 文体は過去のデータを踏襲し、ややメタ認知的な視点や、少し自虐的・ユーモラスな比喩（例：財務省（妻）、アルティメット半端🍆、ＳＯＳなど）、ビジネス用語と日常のギャップ（例：損益分岐点、ＲＯＩ、アハ体験等）を織り交ぜること。
4. 本文中の思考の転換や段落の間には「▼」を必ず挟むこと（過去のフォーマットに完全に倣う）。
5. 出力は以下のJSONフォーマットのみとすること。他の説明や前置きテキストは一切不要。
{{
  "title": "タイトル（10-12文字）",
  "body": "本文（680-700文字）"
}}
"""
    
    user_prompt = f"【テーマ】\n{theme}\n\n【内容】\n{content}\n\n【過去の文章データ（一部）】\n{archive_data}"

    payload = {
        "contents": [
            {"role": "user", "parts": [{"text": system_prompt + "\n" + user_prompt}]}
        ],
        "generationConfig": {"temperature": 0.7}
    }
    
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json"})
    context = ssl._create_unverified_context()
    
    try:
        with urllib.request.urlopen(req, context=context) as response:
            res_data = json.loads(response.read().decode("utf-8"))
            generated_text = res_data["candidates"][0]["content"]["parts"][0]["text"]
            
            # Markdownのコードブロックタグが含まれている場合は除去
            generated_text = generated_text.replace("```json", "").replace("```", "").strip()
            return json.loads(generated_text)
            
    except urllib.error.HTTPError as e:
        print(f"❌ Gemini APIとの通信でエラーが発生しました: {e.code} - {e.read().decode('utf-8')}")
        return None
    except json.JSONDecodeError as e:
        print(f"❌ 生成結果のJSON解析に失敗しました: {e} \n(Raw text: {generated_text})")
        return None
    except Exception as e:
        print(f"❌ 文章生成に失敗しました: {e}")
        return None

def save_to_notion(title, body):
    print("\n📝 Notionへ自動保存しています...")
    url = f"https://api.notion.com/v1/blocks/{ARCHIVE_PAGE_ID}/children"
    
    headers = {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json"
    }
    
    today_str = datetime.datetime.now().strftime("%Y-%m-%d")
    heading_text = f"{today_str} 自動生成分"
    
    # 複数段落の対応（改行で分割してparagraphの配列を作成）
    body_paragraphs = body.split("\n")
    
    # 子ブロックとして、タイトルと本文を追加
    children_blocks = [
        {
            "object": "block",
            "type": "heading_3",
            "heading_3": {
                "rich_text": [{"type": "text", "text": {"content": heading_text}}],
                "color": "blue_background"
            }
        },
        {
            "object": "block",
            "type": "paragraph",
            "paragraph": {
                "rich_text": [
                    {"type": "text", "text": {"content": "◽️要約(" + str(len(title)) + "文字)\n"}, "annotations": {"bold": True}},
                    {"type": "text", "text": {"content": title}}
                ]
            }
        },
        {
            "object": "block",
            "type": "paragraph",
            "paragraph": {
                "rich_text": [
                    {"type": "text", "text": {"content": "◽️本文(" + str(len(body.replace('\n','').replace('▼',''))) + "文字)\n"}, "annotations": {"bold": True}},
                ]
            }
        }
    ]
    
    # 本文をパラグラフごとにブロックとして追加
    for para in body_paragraphs:
        if para.strip() == "▼":
            children_blocks.append({
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [{"type": "text", "text": {"content": "▼"}}]
                }
            })
        elif para.strip():
            children_blocks.append({
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [{"type": "text", "text": {"content": para}}]
                }
            })
            
    # 区切り線
    children_blocks.append({
        "object": "block",
        "type": "divider",
        "divider": {}
    })

    payload = {
        "children": children_blocks
    }
    
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="PATCH")
    context = ssl._create_unverified_context()

    try:
        with urllib.request.urlopen(req, context=context) as response:
            print("✅ Notionへの保存が完了しました！ブラウザでArchiveページの一番下をご確認ください。")
    except urllib.error.HTTPError as e:
        print(f"❌ Notionへの保存でHTTPエラーが発生しました: {e.code} - {e.read().decode('utf-8')}")
    except Exception as e:
        print(f"❌ Notionへの保存に失敗しました: {e}")


import sys

def main():
    print("==========================================")
    print("  ✨ 文トレ自動生成アシスタント 起動 ✨  ")
    print("==========================================")
    
    api_key = get_gemini_key()
    if not api_key:
        print("処理を中断します。")
        return
        
    # Extract from args if provided (useful for AI execution)
    if len(sys.argv) >= 3:
        theme = sys.argv[1]
        content = sys.argv[2]
        print(f"\n📝 テーマ: {theme}")
        print(f"💬 内容: {content}")
    else:
        print("\nどんな文章を書きますか？")
        theme = input("📝 テーマ（例：塾の先生との対話）\n> ")
        if not theme.strip():
            print("テーマが未入力のため終了します。")
            return
            
        content = input("\n💬 内容（例：多岐にわたり6時間半も語り合った）\n> ")
        if not content.strip():
            print("内容が未入力のため終了します。")
            return

    result = generate_text(theme, content, api_key)
    
    if result:
        print("\n=== ✨ 生成された文章 ✨ ===")
        print(f"【タイトル】: {result.get('title', '')}")
        print(f"【本文】:\n{result.get('body', '')}")
        print("===============================\n")
        
        save_to_notion(result.get('title', ''), result.get('body', ''))

if __name__ == "__main__":
    main()
