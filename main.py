import os
import time
import pandas as pd
from datetime import datetime
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

# ===== 設定 =====
BASE_URL = "https://kouen.sports.metro.tokyo.lg.jp/web/"
CSV_FILE = "account.csv"
SCREENSHOT_DIR = "screenshots"
STEP_TIMEOUT = 100000_000

PARK_CODE = {
    "日比谷公園":               "1301000",
    "芝公園":                   "1301010",
    "猿江恩賜公園":             "1301040",
    "亀戸中央公園":             "1301050",
    "木場公園":                 "1301060",
    "祖師谷公園":               "1301070",
    "東白鬚公園":               "1301090",
    "浮間公園":                 "1301100",
    "城北中央公園":             "1301110",
    "赤塚公園":                 "1301120",
    "東綾瀬公園":               "1301130",
    "舎人公園":                 "1301140",
    "篠崎公園Ａ":               "1301150",
    "大島小松川公園":           "1301160",
    "汐入公園":                 "1301170",
    "高井戸公園":               "1301175",
    "善福寺川緑地":             "1301180",
    "光が丘公園":               "1301190",
    "石神井公園Ｂ":             "1301205",
    "井の頭恩賜公園":           "1301220",
    "武蔵野中央公園":           "1301230",
    "小金井公園":               "1301240",
    "野川公園":                 "1301260",
    "府中の森公園":             "1301270",
    "東大和南公園":             "1301280",
    "大井ふ頭中央海浜公園Ｂ":   "1301315",
    "有明テニスＣ人工芝コート": "1301360",
}

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

# ===== 1件分の抽選申込み処理 =====
def apply_one(page, user_id: str, park_name: str, target_date: str, target_time: int, apply_no: int = 1):
#def apply_one(page, user_id: str, park_name: str, target_date: str, target_time: int):
    park_code = PARK_CODE.get(park_name)
    if not park_code:
        raise Exception(f"公園名が辞書に見つかりません: {park_name}")

    # ── 公園を選択
    log(user_id, f"公園を選択: {park_name}")
    page.evaluate(f"""
        const sel = document.querySelector("select#bname");
        sel.value = '{park_code}';
        changeBname(document.form1);
    """)
    page.wait_for_timeout(3000)

    # ── 施設を選択（テニス（人工芝））
    log(user_id, "施設を選択: テニス（人工芝）")
    page.evaluate("""
        const sel = document.querySelector("select#iname");
        sel.value = sel.options[1].value;
        changeIname(document.form1, gLotWTransLotInstSrchVacantAjaxAction);
    """)
    page.wait_for_timeout(3000)

    # ── 対象日・時間のセルを選択
    yyyy, mm, dd = str(target_date).split("/")
    target_ymd = f"{yyyy}{mm}{dd}"
    time_to_koma = {9: 1, 11: 2, 13: 3, 15: 4, 17: 5, 19: 6}
    koma_no = time_to_koma.get(int(target_time))
    if not koma_no:
        raise Exception(f"対応するkomaNoが見つかりません: {target_time}")

    log(user_id, f"対象日: {target_ymd}, 時間帯: {target_time}時→komaNo={koma_no}")

    for _ in range(5):
        dates = page.evaluate("""
            Array.from(document.querySelectorAll('input[name="selectUseYMD"]'))
                .map(el => el.value)
        """)
        log(user_id, f"表示中の日付: {dates}")
        if target_ymd in dates:
            break
        log(user_id, "翌週へ移動...")
        page.locator("button#next-week").click()
        page.wait_for_timeout(2000)
    else:
        raise Exception(f"対象日 {target_ymd} が見つかりませんでした")

    col_index = page.evaluate(f"""
        Array.from(document.querySelectorAll('input[name="selectUseYMD"]'))
            .findIndex(el => el.value === '{target_ymd}')
    """)
    log(user_id, f"列インデックス: {col_index}")

    row_selector = f"tr#usedate-bheader-{koma_no}"
    page.locator(f"{row_selector} td").nth(col_index).click()
    page.wait_for_timeout(1000)

    # ── 「申込み」ボタンをクリック
    log(user_id, "「申込み」ボタンをクリック...")
    page.locator("button#btn-go").click()
    page.wait_for_load_state("networkidle", timeout=STEP_TIMEOUT)

    # ── 申込み番号を選択
    log(user_id, "申込み番号を選択...")
    apply_value = f"{apply_no}-1"
    page.locator("select[name='applyHopeNo']").click()
    page.wait_for_timeout(500)
    page.locator("select[name='applyHopeNo']").select_option(value=apply_value)
    page.wait_for_timeout(500)

    page.evaluate(f"""
        const obj = document.form1;
        obj.applyHopeNo.value = '{apply_value}';
        var result = obj.applyHopeNo.value.split('-');
        obj.selectApplyNo.value = result[0];
        obj.selectHopeNo.value = result[1];
    """)

    # ── 送信
    log(user_id, "申込みを送信...")
    page.once("dialog", lambda dialog: dialog.accept())
    page.wait_for_timeout(1000)
    page.locator("button#btn-go").click()

    # reCAPTCHAが出た場合に手動で解いてもらう
    log(user_id, "⚠️ reCAPTCHAが表示された場合は手動でチェックしてください")
    try:
        # reCAPTCHA完了後またはそのままnetworkidleになるまで待機
        page.wait_for_load_state("networkidle", timeout=60_000)
    except PlaywrightTimeoutError:
        # タイムアウトしても続行（手動操作中の可能性）
        page.wait_for_load_state("networkidle", timeout=STEP_TIMEOUT)

    log(user_id, f"ダイアログ処理完了")
    
    # ── 完了確認＆スクリーンショット
    save_screenshot(page, user_id, f"完了_{park_name}")
    log(user_id, f"=== 申込み完了: {park_name} {target_date} {target_time}時 ===")
    print(page.locator("main").inner_text()[:300])

# ===== メイン処理 =====
def run_check(playwright, account: dict) -> bool:
    user_id  = str(account["user_id"])
    password = str(account["password"])
    CHROME_PROFILE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "chrome_profile")
    # Chromeが完全に閉じている状態で実行すること
    context = playwright.chromium.launch_persistent_context(
        user_data_dir=CHROME_PROFILE_DIR,
        channel="chrome",
        headless=False,
        args=["--disable-blink-features=AutomationControlled"],
        locale="ja-JP",
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
    context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    page = context.new_page()

    """
    browser = playwright.chromium.launch(
        headless=False,# DockerのときはTrue
        args=["--disable-blink-features=AutomationControlled"]
    )
    context = browser.new_context(
        locale="ja-JP",
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
    context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    page = context.new_page()
    """

    try:
        # ── 1. トップページへ移動（Sorryページ / about:blank はリトライ）
        log(user_id, "サイトへアクセス中...")
        MAX_RETRY = 30
        for attempt in range(1, MAX_RETRY + 1):
            try:
                page.goto(BASE_URL, timeout=STEP_TIMEOUT)
                page.wait_for_load_state("networkidle", timeout=STEP_TIMEOUT)
            except PlaywrightTimeoutError:
                log(user_id, f"ページ読み込みタイムアウト、リトライ中... ({attempt}/{MAX_RETRY})")
                time.sleep(3)
                continue

            current_url = page.url
            content = page.content().lower()

            if current_url == "about:blank":
                log(user_id, f"about:blank 検出、リトライ中... ({attempt}/{MAX_RETRY})")
                time.sleep(3)
                continue
            if "sorry" in current_url.lower() or "アクセスできません" in content:
                log(user_id, f"Sorryページ検出、リトライ中... ({attempt}/{MAX_RETRY})")
                time.sleep(1.1)
                continue

            log(user_id, "サイトへのアクセス成功")
            break
        else:
            raise Exception("サイトへのアクセスに失敗しました（about:blank / Sorryページ）")

        # ── 2. ログインボタン押下
        log(user_id, "ログイン画面へ移動中...")
        page.locator("#btn-login").click()
        page.wait_for_load_state("networkidle", timeout=STEP_TIMEOUT)

        # ── 3. ID・パスワード入力 → ログイン
        log(user_id, "ログイン中...")
        page.fill('input[name="userId"]', user_id, timeout=STEP_TIMEOUT)
        page.fill('input[name="password"]', password)
        page.locator("#btn-go").click()
        page.wait_for_load_state("networkidle", timeout=STEP_TIMEOUT)

        # ── 4. 「抽選」メニューをクリック
        log(user_id, "「抽選」メニューを開く...")
        page.locator("a.dropdown-toggle", has_text="抽選").click()
        page.wait_for_timeout(500)

        # ── 5. 「抽選申込み」をクリック
        log(user_id, "「抽選申込み」をクリック...")
        page.get_by_role("link", name="抽選申込み").first.click()
        page.wait_for_load_state("networkidle", timeout=STEP_TIMEOUT)

        # ── 6. 「テニス（人工芝）」の申込みボタンをクリック
        log(user_id, "「テニス（人工芝）」申込みボタンをクリック...")
        page.locator("button.btn-primary[onclick='javascript:doLotEntry(\"130\")']").click()
        page.wait_for_load_state("networkidle", timeout=STEP_TIMEOUT)

        # ── 7. 1件目の申込み
        log(user_id, "=== 1件目の申込み開始 ===")
        apply_one(
            page, user_id,
            str(account["park_name1"]),
            str(account["target_date1"]),
            int(account["target_time1"]),
            apply_no=1
        )

        # ── 8. 「続けて申込み」ボタンをクリックして2件目へ
        log(user_id, "「続けて申込み」ボタンをクリック...")
        page.wait_for_timeout(3000)  # ← 追加
        page.get_by_role("button", name="続けて申込み").click()
        page.wait_for_load_state("networkidle", timeout=STEP_TIMEOUT)

        # ── 9. 2件目の申込み
        log(user_id, "=== 2件目の申込み開始 ===")
        apply_one(
            page, user_id,
            str(account["park_name2"]),
            str(account["target_date2"]),
            int(account["target_time2"]),
            apply_no=2
        )

        log(user_id, "✅ 全申込み完了")
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
        context.close()
        #browser.close()

# ===== エントリーポイント =====
def main():
    if not os.path.exists(CSV_FILE):
        print(f"エラー: {CSV_FILE} が見つかりません。")
        return

    df = pd.read_csv(CSV_FILE)
    required = {"user_id", "password", "park_name1", "target_date1", "target_time1",
                "park_name2", "target_date2", "target_time2"}
    missing = required - set(df.columns)
    if missing:
        print(f"エラー: CSV に必要なカラムが不足しています → {missing}")
        return

    results = []
    with sync_playwright() as playwright:
        for _, row in df.iterrows():
            ok = run_check(playwright, row)
            results.append({"user_id": row["user_id"], "success": ok})
            time.sleep(2)

    print("\n===== 実行結果サマリー =====")
    for r in results:
        status = "✅ 成功" if r["success"] else "❌ 失敗"
        print(f"  {r['user_id']}: {status}")
    total = len(results)
    success = sum(1 for r in results if r["success"])
    print(f"\n{total} 件中 {success} 件成功\n")

if __name__ == "__main__":
    main()