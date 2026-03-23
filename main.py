import os
import time
import pandas as pd
from datetime import datetime
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

# ===== 設定 =====
BASE_URL = "https://kouen.sports.metro.tokyo.lg.jp/web/"
CSV_FILE = "account.csv"
SCREENSHOT_DIR = "screenshots"
STEP_TIMEOUT = 180_000  # 各操作のタイムアウト（ms）

# ===== ログ出力ヘルパー =====
def log(user_id: str, msg: str):
	ts = datetime.now().strftime("%H:%M:%S")
	print(f"[{ts}][{user_id}] {msg}")

def save_screenshot(page, user_id: str, label: str = ""):
	os.makedirs(SCREENSHOT_DIR, exist_ok=True)
	ts = datetime.now().strftime("%Y%m%d_%H%M%S")
	suffix = f"_{label}" if label else ""
	path = os.path.join(SCREENSHOT_DIR, f"{user_id}{suffix}_{ts}.png")
	page.screenshot(path=path, full_page=True)
	log(user_id, f"スクリーンショット保存: {path}")
	return path

# ===== メイン処理 =====
def run_check(playwright, account: dict) -> bool:
	"""
	1アカウント分の抽選申し込み確認画面キャプチャを実行する。
	成功時 True、失敗時 False を返す。
	"""
	user_id  = str(account["user_id"])
	password = str(account["password"])

	browser = playwright.chromium.launch(headless=True)  # 動作確認しやすいよう headless=False
	context = browser.new_context(locale="ja-JP")
	page	= context.new_page()

	try:
		"""
		# ── 1. トップページへ移動 ──────────────────────────────────────
		log(user_id, "サイトへアクセス中...")
		page.goto(BASE_URL, timeout=STEP_TIMEOUT)
		page.wait_for_load_state("networkidle")
		"""
		# ── 1. トップページへ移動（sorryページの場合はリトライ）────────
		log(user_id, "サイトへアクセス中...")
		MAX_RETRY = 30
		for attempt in range(1, MAX_RETRY + 1):
			page.goto(BASE_URL, timeout=STEP_TIMEOUT)
			page.wait_for_load_state("networkidle")
			if "アクセスできません" not in page.content().lower():
				break
			log(user_id, f"Sorryページ検出、リトライ中... ({attempt}/{MAX_RETRY})")
			time.sleep(1.1)
		else:
			raise Exception("Sorryページから抜け出せませんでした")

		# ── 2. ログインボタン押下（ヘッダー）─────────────────────────────
		log(user_id, "ログイン画面へ移動中...")
		page.locator("#btn-login").click()
		page.wait_for_load_state("networkidle")

		# ── 3. ID・パスワード入力 → ログイン ─────────────────────────
		log(user_id, "ログイン中...")
		page.fill('input[name="userId"]', user_id, timeout=STEP_TIMEOUT)
		page.fill('input[name="password"]', password)
		page.locator("#btn-go").click()  # フォーム送信ボタン
		page.wait_for_load_state("networkidle")
		
		# ── 4. 「抽選」メニューをクリック ────────────────────────────
		log(user_id, "「抽選」メニューを開く...")
		page.locator("a.dropdown-toggle", has_text="抽選").click()
		page.wait_for_timeout(500)  # ドロップダウン展開待ち

		# ── 5. 「抽選申し込みの確認」をクリック ─────────────────────
		log(user_id, "「抽選申し込みの確認」へ移動...")
		page.get_by_role("link", name="抽選申込みの確認").click()  # 「申し込み」→「申込み」に修正
		page.wait_for_load_state("networkidle")

		# ── 6. 「マイメニュー」をクリックしてユーザー名を表示 ────────
		log(user_id, "「マイメニュー」を開く...")
		page.locator("#userName").click()

		# マイメニューのドロップダウンが表示されるまで少し待機
		page.wait_for_timeout(500)

		# ── 7. スクリーンショット保存 ────────────────────────────────
		save_screenshot(page, user_id, "抽選申込確認")
		log(user_id, "✅ キャプチャ完了！")
		return True

	except PlaywrightTimeoutError as e:
		log(user_id, f"❌ タイムアウト: {e}")
		save_screenshot(page, user_id, "error_timeout")
		return False
	except Exception as e:
		log(user_id, f"❌ エラー: {e}")
		save_screenshot(page, user_id, "error")
		return False
	finally:
		browser.close()

# ===== エントリーポイント =====
def main():
	if not os.path.exists(CSV_FILE):
		print(f"エラー: {CSV_FILE} が見つかりません。")
		return

	df = pd.read_csv(CSV_FILE)

	# 必須カラムチェック（今回使用するカラムのみ）
	required = {"user_id", "password"}
	missing = required - set(df.columns)
	if missing:
		print(f"エラー: CSV に必要なカラムが不足しています → {missing}")
		return

	results = []
	with sync_playwright() as playwright:
		for _, row in df.iterrows():
			ok = run_check(playwright, row)
			results.append({"user_id": row["user_id"], "success": ok})
			time.sleep(2)  # サーバー負荷軽減

	# サマリー出力
	print("\n===== 実行結果サマリー =====")
	for r in results:
		status = "✅ 成功" if r["success"] else "❌ 失敗"
		print(f"  {r['user_id']}: {status}")
	total = len(results)
	success = sum(1 for r in results if r["success"])
	print(f"\n{total} 件中 {success} 件成功\n")

if __name__ == "__main__":
	main()