# -*- coding: utf-8 -*-
import base64
import csv
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import List, Optional

try:
    from PIL import Image, ImageDraw, ImageFilter, ImageFont
except ImportError:
    Image = None
    ImageDraw = None
    ImageFilter = None
    ImageFont = None

NEWLINE = chr(10)
DEFAULT_ROOT = "D:/lenovo/ai_workbench_outputs"
DEFAULT_BASE_URL = "https://your-api-base-url.example.com/v1"
DEFAULT_MAIN_MODEL = "gpt-5.5"
DEFAULT_IMAGE_MODEL = "gpt-image-2"
RESOLUTION_LEVELS = ["鏍囧噯", "2K", "4K"]
RESOLUTION_SIZE_MAP = {"2K": "2048x2048", "4K": "3840x3840"}
UNSUPPORTED_RESOLUTION_MESSAGE = "褰撳墠鎺ュ彛鍙兘涓嶆敮鎸佽鍒嗚鲸鐜囷紝璇峰垏鎹㈠埌鏍囧噯鍒嗚鲸鐜囨垨纭涓浆绔欐槸鍚︽敮鎸?2K/4K銆?
MAX_EDGE_RESOLUTION_MESSAGE = "褰撳墠鎺ュ彛鏈€楂樻敮鎸?3840 杈归暱锛屽凡涓嶆敮鎸?4096x4096锛岃浣跨敤 3840x3840 鐨?4K 妯″紡銆?

PROJECT_STATUS = ["寰呭紑濮?, "鐢熸垚涓?, "寰呯瓫閫?, "寰呬慨鏀?, "寰呬氦浠?, "宸蹭氦浠?, "宸茬粨绠?, "宸插綊妗?]
IMAGE_STATUS = ["鏈瓫閫?, "鏀惰棌", "娣樻卑", "寰呬慨鏀?, "浜や粯鍥?, "澶囩敤鍥?]
CUSTOMER_TAGS = ["楂樻綔鍔?, "浣庝环鏁忔劅", "闅炬矡閫?, "鍙璐?, "闀挎湡鍚堜綔", "浣撻獙鍗?]
PLATFORMS = ["娣樺疂", "鎷煎澶?, "鎶栭煶灏忓簵", "灏忕孩涔?, "瑙嗛鍙?, "1688", "浜氶┈閫?, "鐙珛绔?, "鍏朵粬"]
USE_CASES = ["涓诲浘", "鍦烘櫙鍥?, "璇︽儏椤?, "灏忕孩涔﹀皝闈?, "鎶栭煶灏侀潰", "妯増 Banner", "鑺傛棩淇冮攢", "鏁村绱犳潗鍖?]
ASPECT_HINTS = ["1:1 鏂瑰浘", "3:4 绔栧浘", "9:16 绔栫増灏侀潰", "16:9 妯増", "璇︽儏椤甸暱鍥炬€濊矾"]
TEXT_POLICIES = ["涓嶇敓鎴愭枃瀛?, "棰勭暀鍚庢湡鍔犲瓧鍖哄煙", "椤堕儴鐣欑櫧缁欐爣棰?, "宸︿晶鐣欑櫧缁欏崠鐐?, "鍙充晶鐣欑櫧缁欏崠鐐?]
COMPOSITION_OPTIONS = ["灞呬腑澶т富浣?, "灞呬腑涓富浣?, "涓讳綋鍋忓乏", "涓讳綋鍋忓彸", "淇媿", "鐗瑰啓", "浣庤搴﹁嫳闆勮瑙?]
BACKGROUND_OPTIONS = ["绾櫧鑳屾櫙", "楂樼骇鎽勫奖妫?, "鍔炲叕妗?, "瀹跺眳鐢熸椿", "鎴峰闇茶惀", "娓呯埥鍐版劅", "绀煎搧閫佺ぜ", "绉戞妧鍐锋劅", "灏忕孩涔︾敓娲荤編瀛?, "鑺傛棩淇冮攢", "妯増骞垮憡鐣欑櫧"]
LIGHT_OPTIONS = ["鏌斿拰妫氭媿鍏?, "鑷劧鏅ㄥ厜", "鏆栬壊鐢靛奖鍏?, "鍐疯壊绉戞妧鍏?, "楂樺姣斿箍鍛婂厜", "娓呯埥钃濊皟鍏?, "濂緢鍝佹殫璋冨厜"]
BANNED_DEFAULT = ["no text", "no watermark", "no messy background", "no logo distortion", "do not change product structure", "no extra random objects", "no deformed product"]
TEMPLATE_INDUSTRIES = ["椋熷搧楗枡", "缇庡鏃ュ寲", "鍐滀骇鍝佺敓椴?, "瀹跺眳灏忓晢鍝?, "璺ㄥ閫氱敤", "鍖呰瀹氬埗", "浜旈噾鏈烘/宸ヤ笟鍝?, "鐭ヨ瘑浜у搧灏侀潰", "瀹犵墿鐢ㄥ搧", "鍏朵粬"]
TEMPLATE_INDUSTRY_TARGETS = {
    "椋熷搧楗枡": 20,
    "缇庡鏃ュ寲": 20,
    "鍐滀骇鍝佺敓椴?: 15,
    "瀹跺眳灏忓晢鍝?: 15,
    "璺ㄥ閫氱敤": 10,
    "鍖呰瀹氬埗": 10,
    "浜旈噾鏈烘/宸ヤ笟鍝?: 5,
    "鐭ヨ瘑浜у搧灏侀潰": 10,
    "瀹犵墿鐢ㄥ搧": 5,
    "鍏朵粬": 0,
}
TEMPLATE_INDUSTRY_ALIASES = {
    "椋熷搧宸ュ巶": "椋熷搧楗枡",
    "鏃ュ寲宸ュ巶": "缇庡鏃ュ寲",
    "鍐滀骇鍝?: "鍐滀骇鍝佺敓椴?,
    "瀹跺叿鍘?: "瀹跺眳灏忓晢鍝?,
    "璺ㄥ鐢靛晢": "璺ㄥ閫氱敤",
    "鍖呰鍘?: "鍖呰瀹氬埗",
    "浜旈噾宸ュ巶": "浜旈噾鏈烘/宸ヤ笟鍝?,
    "鏈烘鍘?: "浜旈噾鏈烘/宸ヤ笟鍝?,
    "灏忕孩涔﹂€氱敤": "鐭ヨ瘑浜у搧灏侀潰",
    "鍏朵粬": "鍏朵粬",
}
TEMPLATE_PURPOSES = ["灏侀潰鍥?, "浜у搧浠嬬粛鍥?, "鍗栫偣鍥?, "淇冮攢娴锋姤", "宸ュ巶瀹炲姏鍥?, "璇︽儏椤靛浘", "娲诲姩鍥?]
TEMPLATE_STYLES = ["楂樼骇绠€绾?, "绉戞妧鎰?, "宸ュ巶瀹炲姏鎰?, "娓呮柊椋?, "鐢靛晢淇冮攢椋?, "鍥芥疆椋?, "鍏朵粬"]
TEMPLATE_LAYOUTS = ["宸︽爣棰樺彸瑙嗚", "椤堕儴鏍囬鍗＄墖鍨?, "涓ぎ澶у瓧鍨?, "涓夊崱鐗囦俊鎭瀷"]
TEMPLATE_PLATFORMS = ["1688", "鎶栭煶", "灏忕孩涔?, "鏈嬪弸鍦?, "鍏紬鍙?, "閫氱敤"]
TEMPLATE_RATIOS = ["1:1", "3:4", "4:5", "9:16", "16:9", "闀垮浘", "鍏朵粬"]

TEMPLATE_SOURCE_SITES = [
    {
        "name": "Pexels",
        "type": "鍏嶈垂鍥惧簱",
        "url": "https://www.pexels.com/search/{query}/",
        "license": "鍋忔憚褰辫儗鏅紝涓嬭浇鍓嶇‘璁?Pexels License锛涢€傚悎鐢熸椿鏂瑰紡鍜屼骇鍝佹皼鍥村弬鑰冦€?,
    },
    {
        "name": "Unsplash",
        "type": "鍏嶈垂鍥惧簱",
        "url": "https://unsplash.com/s/photos/{query}",
        "license": "鍋忛珮璐ㄩ噺鎽勫奖锛岄€傚悎鑳屾櫙鍜屽弬鑰冿紱娉ㄦ剰浜虹墿鑲栧儚銆佸搧鐗屾爣璇嗗拰鏁忔劅鐢ㄩ€斻€?,
    },
    {
        "name": "Pixabay",
        "type": "鍏嶈垂鍥惧簱/鐭㈤噺",
        "url": "https://pixabay.com/images/search/{query}/",
        "license": "鍙壘鑳屾櫙銆佺煝閲忋€佹彃鐢伙紱涓嬭浇鍓嶇‘璁?Pixabay License銆?,
    },
    {
        "name": "Freepik",
        "type": "鍏嶈垂/浠樿垂绱犳潗",
        "url": "https://www.freepik.com/search?format=search&query={query}",
        "license": "妯℃澘鍜岀煝閲忓锛涘厤璐归€氬父闇€缃插悕锛孭remium 涔熸湁杞敭闄愬埗锛屽繀椤荤湅鎺堟潈銆?,
    },
    {
        "name": "Envato Elements",
        "type": "浠樿垂妯℃澘",
        "url": "https://elements.envato.com/search/{query}",
        "license": "閫傚悎姝ｅ紡鍟嗙敤绱犳潗搴擄紱纭璁㈤槄鎺堟潈銆侀」鐩敞鍐屽拰瀹㈡埛浜や粯鑼冨洿銆?,
    },
    {
        "name": "Adobe Stock",
        "type": "浠樿垂鍥惧簱",
        "url": "https://stock.adobe.com/search?k={query}",
        "license": "鎺堟潈娓呮櫚浣嗘垚鏈珮锛涢€傚悎楂樹环鍊煎鎴峰拰鍏抽敭鐗╂枡銆?,
    },
    {
        "name": "Canva",
        "type": "鍦ㄧ嚎妯℃澘",
        "url": "https://www.canva.com/templates/search/{query}/",
        "license": "閫傚悎鍙傝€冪増寮忥紱涓嶈鐩存帴杞敭妯℃澘锛屾寜 Canva 鎺堟潈鑼冨洿浣跨敤銆?,
    },
    {
        "name": "绋垮畾璁捐",
        "type": "涓枃妯℃澘",
        "url": "https://www.gaoding.com/templates/search/{query}",
        "license": "涓枃鐢靛晢妯℃澘澶氾紱涓嬭浇鍜屼氦浠樺墠纭浼氬憳鍟嗙敤鎺堟潈銆?,
    },
    {
        "name": "鍒涘璐?,
        "type": "涓枃妯℃澘",
        "url": "https://www.chuangkit.com/designtools/search/{query}",
        "license": "閫傚悎涓枃淇冮攢鍙傝€冿紱娉ㄦ剰浼氬憳鎺堟潈銆佷簩鏀瑰拰瀹㈡埛浜や粯闄愬埗銆?,
    },
]

TEMPLATE_SOURCE_KEYWORDS = {
    "椋熷搧楗枡": [
        "food product poster background no text",
        "beverage product advertising background no text",
        "fresh snack packaging poster background",
        "healthy food promotion background blank layout",
    ],
    "缇庡鏃ュ寲": [
        "skincare product poster background no text",
        "cosmetic product display background",
        "clean beauty advertising background",
        "daily chemical product poster background",
    ],
    "鍐滀骇鍝佺敓椴?: [
        "fresh agriculture product poster background no text",
        "organic farm product advertising background",
        "fresh fruit vegetable poster background",
        "rural agricultural product background",
    ],
    "瀹跺眳灏忓晢鍝?: [
        "home goods product poster background no text",
        "household product advertising background",
        "clean home lifestyle product background",
        "storage organizer product display background",
    ],
    "璺ㄥ閫氱敤": [
        "ecommerce product banner background no text",
        "amazon product listing background",
        "modern product showcase background",
        "clean product advertising template background",
    ],
    "鍖呰瀹氬埗": [
        "packaging factory poster background",
        "custom packaging product display background",
        "cardboard box advertising background",
        "gift box packaging showcase background",
    ],
    "浜旈噾鏈烘/宸ヤ笟鍝?: [
        "industrial product advertising background no text",
        "manufacturing factory poster background",
        "machinery product banner background",
        "hardware tools product display background",
    ],
    "鐭ヨ瘑浜у搧灏侀潰": [
        "online course cover background no text",
        "AI tutorial poster background no text",
        "digital product course cover template background",
        "SaaS documentation poster background",
    ],
    "瀹犵墿鐢ㄥ搧": [
        "pet product poster background no text",
        "pet supplies advertising background",
        "cat dog product display background",
        "pet food promotion background blank layout",
    ],
    "鍏朵粬": ["product advertising background no text", "blank poster background"],
}

TEMPLATE_AI_SCENE_PROMPTS = {
    "椋熷搧楗枡": "fresh premium food and beverage product promotion background, appetizing clean lighting, supermarket and live commerce friendly",
    "缇庡鏃ュ寲": "clean skincare and daily care product display background, soft studio light, premium beauty aesthetic",
    "鍐滀骇鍝佺敓椴?: "fresh farm product and organic agriculture poster background, natural daylight, healthy green atmosphere",
    "瀹跺眳灏忓晢鍝?: "modern home lifestyle product background, clean room scene, warm practical ecommerce composition",
    "璺ㄥ閫氱敤": "modern ecommerce product showcase background, global marketplace advertising style, clean conversion-focused layout",
    "鍖呰瀹氬埗": "custom packaging factory and gift box display background, material showcase, B2B trustworthy composition",
    "浜旈噾鏈烘/宸ヤ笟鍝?: "industrial manufacturing product advertising background, factory strength, reliable B2B visual style",
    "鐭ヨ瘑浜у搧灏侀潰": "digital course cover and AI tutorial poster background, SaaS documentation style, modern knowledge product layout",
    "瀹犵墿鐢ㄥ搧": "pet supplies product advertising background, warm clean lifestyle scene, friendly pet ecommerce layout",
    "鍏朵粬": "clean commercial product poster background, blank layout for local text overlay",
}

TEMPLATE_AI_PROMPT_SUFFIX = "no readable text, no Chinese characters, no English letters, blank title area, clear semi-transparent title card area, abstract placeholder lines only, product advertising background, professional commercial poster layout, high readability, no logo, no watermark"

STYLE_PRESETS = {
    "楂樼骇绠€绾?: "premium, minimal, clean, high-end commercial photography, realistic, sharp focus",
    "绉戞妧鍐锋劅": "futuristic, clean, cool lighting, premium technology advertising, realistic, high contrast",
    "娓╂殩鐢熸椿": "warm, cozy, natural daylight, lifestyle photography, realistic, elegant",
    "濂緢鍝佹劅": "luxury, refined, cinematic lighting, elegant shadows, premium brand advertising, photorealistic",
    "娓呯埥骞磋交": "fresh, bright, clean, youthful, refreshing commercial photography, realistic",
    "鍥芥疆璐ㄦ劅": "modern Chinese aesthetic, elegant, premium, tasteful props, refined commercial photography",
}

SCENE_TEMPLATES = {
    "鐧藉簳涓诲浘": "centered on a pure white background, soft diffused studio lighting, realistic material texture, subtle natural shadow, premium e-commerce main image",
    "楂樼骇鎽勫奖妫?: "placed on a minimal premium platform, elegant background, soft cinematic studio lighting, refined commercial product photography",
    "鍔炲叕妗屽満鏅?: "on a clean modern office desk, laptop and notebook softly blurred in the background, soft morning daylight, premium lifestyle commercial photography",
    "瀹跺眳鐢熸椿": "in a clean modern home scene, natural daylight, warm premium atmosphere, realistic lifestyle product photography",
    "鎴峰闇茶惀": "on a wooden camping table, forest background bokeh, morning sunlight, light mist, premium outdoor advertising photography",
    "娓呯埥鍐版劅": "with cool tones, ice cubes, water droplets, fresh clean atmosphere, refreshing summer advertising style",
    "绀煎搧閫佺ぜ": "with elegant gift packaging elements, tasteful props, warm lighting, refined premium gift style commercial photography",
    "灏忕孩涔︾鑽?: "on soft fabric with books, flowers, and natural daylight, clean aesthetic composition, cozy Xiaohongshu style lifestyle photography",
    "鎶栭煶灏侀潰": "vertical short video cover composition, strong central product placement, clean bright background, eye-catching lighting, high visual impact",
    "妯増 Banner": "wide horizontal advertising composition, product slightly off-center, clean negative space reserved for future text, premium commercial banner style",
    "璇︽儏椤靛崠鐐瑰浘": "clean e-commerce detail page style, product clearly visible, space reserved for feature callouts, premium product photography, no embedded text",
    "鑺傛棩淇冮攢": "premium festive advertising scene, tasteful props, warm luxury lighting, clean commercial composition, no embedded text",
}

PRODUCT_EXAMPLES = {
    "淇濇俯鏉?: "a matte black stainless steel insulated water bottle, modern shape, realistic metal texture",
    "棣欐按": "a luxury transparent perfume bottle with a silver cap, elegant glass texture, premium packaging",
    "鎶よ偆鍝?: "a premium white skincare serum bottle with a minimalist label, clean beauty product packaging",
    "鍜栧暋鏉?: "a white ceramic coffee cup, glossy ceramic texture, simple elegant shape",
    "灏忓鐢?: "a compact white smart home appliance, clean modern design, realistic plastic and metal texture",
    "椋熷搧鍖呰": "a premium snack package, clean packaging design, realistic commercial product texture",
}

PHRASES = {
    "鍒濇绉佷俊": "鑰佹澘浣犲ソ锛屾垜鐪嬩簡涓嬩綘浠繖娆句骇鍝侊紝浜у搧鏈韩涓嶉敊锛屼絾鐜板湪涓诲浘鍜屽満鏅浘杩樻湁鍗囩骇绌洪棿銆傛垜杩欒竟鍙互鐢?AI 鍟嗕笟鎽勫奖鏂瑰紡甯綘鍋氫竴鐗堟洿楂樼骇鐨勪骇鍝佸浘锛屽彲浠ュ厛鍑轰竴寮犳牱鍥撅紝浣犺寰楀彲浠ュ啀鍚堜綔銆?,
    "鎶ヤ环璇存槑": "杩欎竴濂楀寘鍚富鍥俱€佸満鏅浘鍜屽皝闈㈠浘锛屽厛鎸変綋楠屼环鍋氥€傛瘡濂楀寘鍚浐瀹氬紶鏁板拰鍥哄畾淇敼娆℃暟锛岃秴鍑轰慨鏀硅寖鍥撮渶瑕佸崟鐙姞璐圭敤銆?,
    "淇敼杈圭晫": "杩欑増鍙互璋冩暣鑳屾櫙銆佸厜褰便€佹瀯鍥惧拰姘涘洿锛屼絾濡傛灉瑕佹眰瀹屽叏淇濈暀浜у搧 Logo銆佸寘瑁呯粏鑺傚拰缁撴瀯涓嶅彉锛岄渶瑕佽蛋鍥剧墖缂栬緫鎴栦汉宸ヤ慨鍥炬祦绋嬶紝鎴愭湰浼氭洿楂樸€?,
    "浜や粯璇濇湳": "鍥剧墖宸茬粡鏁寸悊濂斤紝閲岄潰鍖呭惈涓诲浘銆佸満鏅浘鍜屽鐢ㄥ浘銆備綘鍙互鍏堢湅鏁翠綋鏂瑰悜锛屽鏋滃彧鍋氬皬鑼冨洿璋冩暣锛屾垜鍙互缁х画甯綘浼樺寲銆?,
    "鎷掔粷浣庝环": "杩欎釜浠锋牸濡傛灉鍙仛涓€寮犳祴璇曞浘鍙互鑰冭檻锛屼絾瀹屾暣涓婃灦绱犳潗闇€瑕佷繚璇佽川閲忓拰淇敼鏃堕棿锛屽お浣庣殑浠锋牸鎴戣繖杈规病娉曚繚璇佷氦浠樻晥鏋溿€?,
}


def dependency_available(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


def uid() -> str:
    return uuid.uuid4().hex[:12]


def now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def stamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def ensure_dir(path_text: str) -> Path:
    path = Path(path_text).expanduser()
    try:
        path.mkdir(parents=True, exist_ok=True)
        return path
    except PermissionError:
        fallback = Path.home() / "Desktop" / "ai_workbench_outputs"
        fallback.mkdir(parents=True, exist_ok=True)
        return fallback


def safe_name(text: str, max_len: int = 60) -> str:
    bad = set(chr(92) + "/:*?" + chr(34) + "<>|")
    result = []
    for ch in str(text).strip():
        result.append("_" if ch in bad or ch.isspace() else ch)
    name = "".join(result)
    while "__" in name:
        name = name.replace("__", "_")
    return name.strip("_")[:max_len] or "untitled"


def data_dir(root: str) -> Path:
    path = ensure_dir(root) / "_data"
    path.mkdir(parents=True, exist_ok=True)
    return path


def json_path(root: str, name: str) -> Path:
    return data_dir(root) / name


def read_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def append_jsonl(path: Path, record: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + NEWLINE)


def load_jsonl(path: Path, limit: int = 200) -> List[dict]:
    if not path.exists():
        return []
    rows = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            try:
                rows.append(json.loads(line.strip()))
            except Exception:
                pass
    return rows[-limit:][::-1]


def open_folder(path_text: str, st_module=None) -> None:
    path = ensure_dir(path_text)
    try:
        if os.name == "nt":
            os.startfile(str(path))
        elif hasattr(os, "uname") and os.uname().sysname == "Darwin":
            subprocess.Popen(["open", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path)])
    except Exception as e:
        if st_module:
            st_module.error(f"鎵撳紑鏂囦欢澶瑰け璐ワ細{e}")
        else:
            print(f"鎵撳紑鏂囦欢澶瑰け璐ワ細{e}")


def save_csv(path: Path, rows: List[dict]) -> None:
    if not rows:
        return
    keys = sorted({key for row in rows for key in row.keys()})
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        writer.writerows(rows)


def load_projects(root: str) -> List[dict]:
    return read_json(json_path(root, "projects.json"), [])


def save_projects(root: str, rows: List[dict]) -> None:
    write_json(json_path(root, "projects.json"), rows)


def load_customers(root: str) -> List[dict]:
    return read_json(json_path(root, "customers.json"), [])


def save_customers(root: str, rows: List[dict]) -> None:
    write_json(json_path(root, "customers.json"), rows)


def load_manifest(project_folder: str) -> List[dict]:
    return read_json(Path(project_folder) / "image_manifest.json", [])


def save_manifest(project_folder: str, rows: List[dict]) -> None:
    write_json(Path(project_folder) / "image_manifest.json", rows)


def templates_dir(root: str) -> Path:
    path = ensure_dir(root) / "templates"
    path.mkdir(parents=True, exist_ok=True)
    return path


def template_exports_dir(root: str) -> Path:
    path = ensure_dir(root) / "template_exports"
    path.mkdir(parents=True, exist_ok=True)
    return path


def templates_index_path(root: str) -> Path:
    return json_path(root, "templates_index.json")


def load_templates(root: str) -> List[dict]:
    return read_json(templates_index_path(root), [])


def save_templates(root: str, rows: List[dict]) -> None:
    write_json(templates_index_path(root), rows)


def normalize_template_industry(industry) -> str:
    industry = str(industry or "").strip()
    if industry in TEMPLATE_INDUSTRIES:
        return industry
    if industry in TEMPLATE_INDUSTRY_ALIASES:
        return TEMPLATE_INDUSTRY_ALIASES[industry]
    return "鍏朵粬"


def normalize_base_url(base_url: str) -> str:
    base_url = str(base_url or "").strip() or DEFAULT_BASE_URL
    wrong_hosts = ["aliabahub.com", "aliyunhub.com"]
    if any(host in base_url for host in wrong_hosts):
        return DEFAULT_BASE_URL
    return base_url.rstrip("/")


def diagnose_api_connection(base_url: str, timeout: int = 20) -> dict:
    import requests
    base_url = normalize_base_url(base_url)
    url = base_url.rstrip("/") + "/responses"
    session = requests.Session()
    session.trust_env = False
    start = time.time()
    try:
        response = session.get(base_url.rstrip("/"), timeout=timeout)
        return {
            "ok": True,
            "url": url,
            "base_url": base_url,
            "status_code": response.status_code,
            "elapsed": round(time.time() - start, 2),
            "message": "鍩虹鍩熷悕鍙繛鎺ワ紱濡傛灉鐢熸垚浠嶅け璐ワ紝閫氬父鏄?API Key銆佹ā鍨嬫潈闄愩€佹帴鍙ｉ檺娴佹垨涓婃父涓存椂鏂紑銆?,
            "preview": response.text[:500],
        }
    except requests.exceptions.ProxyError as e:
        return {"ok": False, "url": url, "base_url": base_url, "elapsed": round(time.time() - start, 2), "message": "浠ｇ悊杩炴帴澶辫触锛氱郴缁熶唬鐞?VPN/缃戠粶浠ｇ悊鏂紑璇锋眰銆?, "error": str(e)}
    except requests.exceptions.SSLError as e:
        return {"ok": False, "url": url, "base_url": base_url, "elapsed": round(time.time() - start, 2), "message": "SSL 杩炴帴澶辫触锛氬彲鑳芥槸浠ｇ悊璇佷功銆佺綉缁滄嫤鎴垨 HTTPS 鎻℃墜寮傚父銆?, "error": str(e)}
    except requests.exceptions.ConnectionError as e:
        return {"ok": False, "url": url, "base_url": base_url, "elapsed": round(time.time() - start, 2), "message": "缃戠粶杩炴帴澶辫触锛氬绔垨涓棿缃戠粶鐩存帴鏂紑锛屾病鏈夎繑鍥?HTTP 鍝嶅簲銆?, "error": str(e)}
    except Exception as e:
        return {"ok": False, "url": url, "base_url": base_url, "elapsed": round(time.time() - start, 2), "message": "鏈煡杩炴帴閿欒銆?, "error": str(e)}


def url_query(text: str) -> str:
    from urllib.parse import quote_plus
    return quote_plus(str(text or "").strip())


def build_template_source_rows(industry: str) -> List[dict]:
    industry = normalize_template_industry(industry)
    rows = []
    for keyword in TEMPLATE_SOURCE_KEYWORDS.get(industry, []):
        for site in TEMPLATE_SOURCE_SITES:
            query = url_query(keyword)
            rows.append({
                "琛屼笟": industry,
                "鐩爣搴撳瓨": TEMPLATE_INDUSTRY_TARGETS.get(industry, 0),
                "鏉ユ簮": site["name"],
                "绫诲瀷": site["type"],
                "鍏抽敭璇?: keyword,
                "鎼滅储閾炬帴": site["url"].format(query=query),
                "鎺堟潈澶囨敞": site["license"],
                "鐢ㄩ€?: "鎵炬棤鏂囧瓧搴曞浘/鑳屾櫙/鐗堝紡鍙傝€冿紝瀵煎叆妯℃澘搴撳悗鏈湴濂椾腑鏂?,
                "鐘舵€?: "寰呯瓫閫?,
            })
    return rows


def build_template_ai_prompts(industry: str, count: int = 10) -> List[str]:
    industry = normalize_template_industry(industry)
    keywords = TEMPLATE_SOURCE_KEYWORDS.get(industry, TEMPLATE_SOURCE_KEYWORDS["鍏朵粬"])
    scene = TEMPLATE_AI_SCENE_PROMPTS.get(industry, TEMPLATE_AI_SCENE_PROMPTS["鍏朵粬"])
    prompts = []
    for idx in range(max(1, int(count))):
        keyword = keywords[idx % len(keywords)]
        prompts.append(f"[{industry} #{idx + 1:02d}] {scene}, {keyword}, {TEMPLATE_AI_PROMPT_SUFFIX}")
    return prompts


COMMERCIAL_GENERATION_MODES = ["鏅€氭ā寮?, "绋冲畾鍟嗕笟鍥?, "楂樼骇瀹ｄ紶鍥?, "妯℃澘搴曞浘", "浣滃搧闆嗗睍绀哄浘"]
PROMPT_COMPLEXITIES = ["绋冲Ε", "鏍囧噯", "楂樼骇"]
COMMERCIAL_PROMPT_BASE = "clean commercial poster layout, professional composition, clear visual hierarchy, high clarity, no readable text, no real words, no Chinese characters, no English letters, no logo, no watermark"
COMMERCIAL_PROMPT_MODE_PARTS = {
    "鏅€氭ā寮?: "",
    "绋冲畾鍟嗕笟鍥?: "realistic commercial product visual, clean background, balanced lighting, simple layout",
    "楂樼骇瀹ｄ紶鍥?: "premium advertising key visual, refined lighting, strong visual focus, elegant negative space",
    "妯℃澘搴曞浘": "blank poster background, left side title area, right side visual focus, suitable for local text overlay",
    "浣滃搧闆嗗睍绀哄浘": "portfolio showcase image, polished interface style, modern presentation, professional case study visual",
}
COMMERCIAL_PROMPT_COMPLEXITY_PARTS = {
    "绋冲Ε": "simple scene, fewer elements, stable composition",
    "鏍囧噯": "moderate detail, clean props, high quality commercial photography",
    "楂樼骇": "premium materials, cinematic lighting, rich but controlled details, high-end brand atmosphere",
}
PROMPT_PRESETS = {
    "涓昏瑙夊浼犲浘": "AI image workbench hero poster, clean commercial key visual, modern product design workspace, blank title area, no text, no logo, no watermark",
    "宸ヤ綔娴佺▼灞曠ず鍥?: "visual workflow poster background, steps from prompt to image to delivery, clean dashboard style, abstract cards, no text, no logo, no watermark",
    "妯℃澘搴撳睍绀哄浘": "template library showcase background, grid of poster thumbnails, clean creative workspace, professional layout, no readable text, no logo, no watermark",
    "鏈湴濂楀瓧涓庨珮娓呭鍑哄浘": "poster production workflow background, local text overlay and HD export concept, sharp clean commercial visual, no text, no logo, no watermark",
    "澶氳涓氶€傞厤鍥?: "multi industry poster background showcase, food beauty agriculture home products pet products, clean segmented layout, no text, no logo, no watermark",
}


def compress_prompt(prompt: str, max_chars: int = 520) -> str:
    prompt = " ".join(str(prompt or "").replace("\n", " ").split())
    parts = [x.strip() for x in prompt.replace("锛?, ",").replace("锛?, ",").split(",") if x.strip()]
    if not parts:
        parts = [prompt] if prompt else []
    keep_terms = ["no text", "no readable text", "no logo", "no watermark", "no chinese", "no english", "blank", "commercial", "poster", "product", "background", "layout"]
    filler_terms = ["ultra", "extremely", "very", "highly", "8k", "4k", "masterpiece", "award-winning", "intricate", "hyper detailed", "best quality"]
    kept = []
    seen = set()
    for part in parts:
        cleaned = part.strip()
        low = cleaned.lower()
        for filler in filler_terms:
            low = low.replace(filler, "")
        key = " ".join(low.split())
        if not key or key in seen:
            continue
        important = any(term in key for term in keep_terms)
        if important or len(kept) < 6:
            kept.append(cleaned)
            seen.add(key)
        if len(", ".join(kept)) >= max_chars:
            break
    compressed = ", ".join(kept) if kept else prompt[:max_chars]
    required_parts = ["no readable text", "no logo", "no watermark"]
    lower = compressed.lower()
    for item in required_parts:
        if item not in lower:
            compressed = (compressed + ", " + item).strip(", ")
            lower = compressed.lower()
    if len(compressed) > max_chars:
        tail = ", no readable text, no logo, no watermark"
        body_limit = max(80, max_chars - len(tail))
        compressed = compressed[:body_limit].rsplit(" ", 1)[0].strip(", ") + tail
    return compressed


def build_commercial_prompt(user_prompt: str, mode: str, complexity: str, max_chars: int = 520) -> str:
    user_prompt = str(user_prompt or "").strip()
    mode = mode if mode in COMMERCIAL_GENERATION_MODES else "绋冲畾鍟嗕笟鍥?
    complexity = complexity if complexity in PROMPT_COMPLEXITIES else "鏍囧噯"
    complexity_limits = {"绋冲Ε": 420, "鏍囧噯": 520, "楂樼骇": 680}
    max_chars = min(max_chars, complexity_limits.get(complexity, 520))
    if mode == "鏅€氭ā寮?:
        return compress_prompt(user_prompt, max_chars)
    parts = [
        user_prompt,
        COMMERCIAL_PROMPT_MODE_PARTS.get(mode, ""),
        COMMERCIAL_PROMPT_COMPLEXITY_PARTS.get(complexity, ""),
        COMMERCIAL_PROMPT_BASE,
    ]
    return compress_prompt(", ".join([p for p in parts if p]), max_chars)


def build_stable_fallback_prompt(user_prompt: str) -> str:
    return build_commercial_prompt(compress_prompt(user_prompt, 360), "绋冲畾鍟嗕笟鍥?, "绋冲Ε", 420)


def classify_generation_error(error_text: str) -> str:
    text = str(error_text or "")
    lower = text.lower()
    if "api key" in lower or "401" in lower or "authorization" in lower:
        return "API Key 缂哄け鎴栨棤鏁?
    if "aliabahub" in lower or "aliyunhub" in lower or "base url" in lower:
        return "Base URL 閿欒"
    if "proxy" in lower or "remotedisconnected" in lower or "connection aborted" in lower or "connectionerror" in lower:
        return "缃戠粶/浠ｇ悊鏂紑"
    if "timeout" in lower or "timed out" in lower:
        return "涓婃父瓒呮椂"
    if "resolution" in lower or "pixel budget" in lower or "longest edge" in lower:
        return "鍒嗚鲸鐜囦笉鏀寔"
    return "鏈煡閿欒"


def project_label(project: dict) -> str:
    return f"{project.get('customer_name', '鏃犲鎴?)} | {project.get('product_name', '鏃犱骇鍝?)} | {project.get('platform', '鏃犲钩鍙?)} | {project.get('status', '鏃犵姸鎬?)}"


def get_project_by_id(projects: List[dict], project_id: str) -> Optional[dict]:
    for project in projects:
        if project.get("id") == project_id:
            return project
    return None


def make_project_folder(root: str, customer: str, product: str, platform: str) -> str:
    folder = f"{stamp()}_{safe_name(customer)}_{safe_name(product)}_{safe_name(platform)}"
    path = ensure_dir(root) / "projects" / folder
    path.mkdir(parents=True, exist_ok=True)
    for sub in ["source", "generated", "selected", "delivery", "reference", "logs"]:
        (path / sub).mkdir(parents=True, exist_ok=True)
    return str(path)


def build_requirement_prompt(product_name: str, product_desc: str, platform: str, use_case: str, aspect: str, background: str, composition: str, light: str, text_policy: str, style_text: str, extra: str, bans: List[str]) -> str:
    platform_part = f"suitable for {platform} {use_case}"
    ban_text = ", ".join(bans)
    return f"Generate a high-quality commercial product image of {product_name}, {product_desc}, {platform_part}, {aspect}, {composition}, {background}, {light}, {text_policy}, {style_text}, {extra}, {ban_text}."


def build_scene_prompt(product_name: str, product_desc: str, scene_name: str, style_name: str, extra: str) -> str:
    scene = SCENE_TEMPLATES.get(scene_name, scene_name)
    style = STYLE_PRESETS.get(style_name, style_name)
    return f"Generate a high-quality commercial product image of {product_name}, {product_desc}, {scene}, {style}, {extra}, no text, no watermark, no logo distortion, no messy background, do not change product structure."


def extract_image_base64_list(data: dict) -> List[str]:
    images = []
    output = data.get("output", [])
    if isinstance(output, list):
        for item in output:
            if not isinstance(item, dict):
                continue
            if item.get("type") == "image_generation_call" and item.get("result"):
                result = item.get("result")
                images.extend(result if isinstance(result, list) else [result])
            content = item.get("content", [])
            if isinstance(content, list):
                for c in content:
                    if not isinstance(c, dict):
                        continue
                    result = c.get("result") or c.get("b64_json") or c.get("image_base64")
                    if result:
                        images.extend(result if isinstance(result, list) else [result])
    data_list = data.get("data", [])
    if isinstance(data_list, list):
        for item in data_list:
            if isinstance(item, dict):
                result = item.get("b64_json") or item.get("image_base64")
                if result:
                    images.append(result)
    return [x for x in images if isinstance(x, str) and x.strip()]


def resolve_generation_size(resolution_level: str, selected_size: str) -> str:
    return RESOLUTION_SIZE_MAP.get(resolution_level, selected_size)


def with_resolution_hint(error_text: str, size: str) -> str:
    normalized_error = error_text.lower()
    if "longest edge" in normalized_error and "3840" in normalized_error:
        return MAX_EDGE_RESOLUTION_MESSAGE
    if size in RESOLUTION_SIZE_MAP.values() and UNSUPPORTED_RESOLUTION_MESSAGE not in error_text:
        return f"{UNSUPPORTED_RESOLUTION_MESSAGE} 鍘熷閿欒锛歿error_text}"
    return error_text


def load_font(size: int, bold: bool = False):
    if ImageFont is None:
        raise RuntimeError("鏈畨瑁?Pillow锛岃鍏堣繍琛岋細pip install pillow")
    font_candidates = [
        r"C:\Windows\Fonts\msyhbd.ttc" if bold else r"C:\Windows\Fonts\msyh.ttc",
        r"C:\Windows\Fonts\simhei.ttf",
        r"C:\Windows\Fonts\arial.ttf",
    ]
    for font_path in font_candidates:
        if font_path and Path(font_path).exists():
            return ImageFont.truetype(font_path, size=size)
    return ImageFont.load_default()


def wrap_text(text: str, font, max_width: int, max_lines: int = 3) -> List[str]:
    lines = []
    current = ""
    for char in str(text or ""):
        test_line = current + char
        bbox = font.getbbox(test_line)
        test_width = bbox[2] - bbox[0]
        if test_width <= max_width:
            current = test_line
        else:
            if current:
                lines.append(current)
            current = char
            if len(lines) >= max_lines:
                break
    if current and len(lines) < max_lines:
        lines.append(current)
    return lines


def add_text_layer_left_title(image_path, title: str, subtitle: str = "", tags: str = "", output_dir=None, output_suffix: str = "_text") -> str:
    if Image is None:
        raise RuntimeError("鏈畨瑁?Pillow锛岃鍏堣繍琛岋細pip install pillow")
    if not any(str(x or "").strip() for x in [title, subtitle, tags]):
        return image_path
    image_path = Path(image_path)
    if not image_path.exists():
        raise FileNotFoundError(f"鍥剧墖鏂囦欢涓嶅瓨鍦細{image_path}")

    with Image.open(image_path) as img:
        img = img.convert("RGBA")
        width, height = img.size
        overlay = Image.new("RGBA", img.size, (255, 255, 255, 0))
        draw = ImageDraw.Draw(overlay)

        margin_x = int(width * 0.07)
        card_y = int(height * 0.16)
        card_w = int(width * 0.48)
        card_h = int(height * 0.62)
        radius = max(18, int(width * 0.025))

        # Semi-transparent card keeps Chinese text readable on busy AI backgrounds.
        draw.rounded_rectangle(
            [margin_x, card_y, margin_x + card_w, card_y + card_h],
            radius=radius,
            fill=(255, 255, 255, 220),
            outline=(220, 245, 238, 190),
            width=max(2, int(width * 0.002)),
        )

        title_font = load_font(max(34, int(width * 0.055)), bold=True)
        subtitle_font = load_font(max(20, int(width * 0.024)), bold=False)
        tag_font = load_font(max(18, int(width * 0.020)), bold=True)

        text_x = margin_x + int(width * 0.035)
        text_y = card_y + int(height * 0.09)
        max_text_width = card_w - int(width * 0.07)

        for line in wrap_text(title, title_font, max_text_width, max_lines=3):
            draw.text((text_x, text_y), line, font=title_font, fill=(16, 35, 31, 255))
            text_y += int(width * 0.072)

        if subtitle:
            text_y += int(height * 0.025)
            for line in wrap_text(subtitle, subtitle_font, max_text_width, max_lines=3):
                draw.text((text_x, text_y), line, font=subtitle_font, fill=(51, 65, 61, 255))
                text_y += int(width * 0.035)

        tag_items = [x.strip() for x in str(tags or "").replace("锛?, ",").split(",") if x.strip()]
        if tag_items:
            text_y += int(height * 0.055)
            tag_x = text_x
            tag_h = max(28, int(width * 0.04))
            for tag in tag_items[:4]:
                tag_text = f" {tag} "
                bbox = tag_font.getbbox(tag_text)
                tag_w = bbox[2] - bbox[0] + int(width * 0.022)
                if tag_x + tag_w > margin_x + card_w - int(width * 0.025):
                    break
                draw.rounded_rectangle(
                    [tag_x, text_y, tag_x + tag_w, text_y + tag_h],
                    radius=int(tag_h / 2),
                    fill=(222, 252, 242, 255),
                )
                draw.text(
                    (tag_x + int(width * 0.011), text_y + int(tag_h * 0.18)),
                    tag_text,
                    font=tag_font,
                    fill=(16, 185, 129, 255),
                )
                tag_x += tag_w + int(width * 0.012)

        result = Image.alpha_composite(img, overlay).convert("RGB")
        if output_dir:
            output_base = Path(output_dir)
            output_base.mkdir(parents=True, exist_ok=True)
            output_path = output_base / f"{image_path.stem}{output_suffix}{image_path.suffix}"
        else:
            output_path = image_path.with_name(f"{image_path.stem}{output_suffix}{image_path.suffix}")
        result.save(output_path, quality=95, optimize=True)
        return str(output_path)


def export_hd_image(image_path, mode: str = "鍘熷浘", output_dir=None) -> str:
    if mode == "鍘熷浘":
        return str(image_path)
    if Image is None:
        raise RuntimeError("鏈畨瑁?Pillow锛岃鍏堣繍琛岋細pip install pillow")
    image_path = Path(image_path)
    if not image_path.exists():
        raise FileNotFoundError(f"鍥剧墖鏂囦欢涓嶅瓨鍦細{image_path}")

    with Image.open(image_path) as img:
        img = img.convert("RGB")
        width, height = img.size
        if mode == "楂樻竻2鍊?:
            new_size = (width * 2, height * 2)
            suffix = "_x2"
        elif mode == "娴锋姤楂樻竻3000":
            ratio = 3000 / max(width, height)
            new_size = (int(width * ratio), int(height * ratio))
            suffix = "_poster_hd_3000"
        elif mode == "娴锋姤楂樻竻3840":
            ratio = 3840 / max(width, height)
            new_size = (int(width * ratio), int(height * ratio))
            suffix = "_poster_hd_3840"
        else:
            return str(image_path)

        resized = img.resize(new_size, Image.Resampling.LANCZOS)
        resized = resized.filter(ImageFilter.UnsharpMask(radius=1.2, percent=120, threshold=3))
        if output_dir:
            output_base = Path(output_dir)
            output_base.mkdir(parents=True, exist_ok=True)
            output_path = output_base / f"{image_path.stem}{suffix}{image_path.suffix}"
        else:
            output_path = image_path.with_name(f"{image_path.stem}{suffix}{image_path.suffix}")
        resized.save(output_path, quality=95, optimize=True)
        return str(output_path)


def render_template_text_left_title(template_file: str, output_dir: Path, title: str, subtitle: str, tags: str, selling_points: List[str], cta: str, contact: str, brand: str, export_mode: str) -> dict:
    title_parts = [x.strip() for x in [brand, title] if x and x.strip()]
    final_title = "锝?.join(title_parts) if title_parts else "宸ュ巶娴锋姤"
    detail_lines = [subtitle.strip()] if subtitle and subtitle.strip() else []
    detail_lines.extend([x.strip() for x in selling_points if x and x.strip()])
    if cta and cta.strip():
        detail_lines.append(cta.strip())
    if contact and contact.strip():
        detail_lines.append(contact.strip())
    final_subtitle = "\n".join(detail_lines)
    text_path = add_text_layer_left_title(template_file, final_title, final_subtitle, tags, output_dir=output_dir, output_suffix=f"_text_{stamp()}")
    hd_path = ""
    final_path = text_path
    if export_mode != "鍘熷浘":
        hd_path = export_hd_image(text_path, export_mode, output_dir=output_dir)
        final_path = hd_path
    return {"text_file": text_path, "hd_file": hd_path, "final_file": final_path}


def post_process_files(files: List[str], export_mode: str, enable_text_layer: bool, poster_title: str, poster_subtitle: str, poster_tags: str) -> dict:
    final_files = []
    text_files = []
    hd_files = []
    errors = []
    for fp in files:
        final_path = fp
        text_path = ""
        hd_path = ""
        if enable_text_layer and any(str(x or "").strip() for x in [poster_title, poster_subtitle, poster_tags]):
            try:
                text_path = add_text_layer_left_title(fp, poster_title, poster_subtitle, poster_tags)
                final_path = text_path
            except Exception as e:
                errors.append(f"鏂囧瓧灞傚け璐?{Path(fp).name}: {e}")
        if export_mode != "鍘熷浘":
            try:
                hd_path = export_hd_image(text_path or fp, export_mode)
                final_path = hd_path
            except Exception as e:
                errors.append(f"楂樻竻瀵煎嚭澶辫触 {Path(fp).name}: {e}")
        final_files.append(final_path)
        text_files.append(text_path)
        hd_files.append(hd_path)
    return {"final_files": final_files, "text_files": text_files, "hd_files": hd_files, "postprocess_errors": errors}


def generate_one(prompt: str, index: int, api_key: str, base_url: str, main_model: str, image_model: str, size: str, quality: str, output_format: str, save_dir: Path, timeout_seconds: int, max_retries: int = 2) -> dict:
    import requests
    base_url = normalize_base_url(base_url)
    url = base_url.rstrip("/") + "/responses"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    start = time.time()
    prompt_plan = [prompt, prompt, build_stable_fallback_prompt(prompt), build_stable_fallback_prompt(prompt)]
    quality_order = ["high", "medium", "low"]
    if quality in quality_order:
        quality_plan = quality_order[quality_order.index(quality):]
    else:
        quality_plan = [quality, "medium", "low"]
    while len(quality_plan) < len(prompt_plan):
        quality_plan.append(quality_plan[-1])
    attempts = max(1, min(int(max_retries) + 1, len(prompt_plan)))
    last_error = ""
    last_prompt = prompt
    last_quality = quality
    for attempt in range(1, attempts + 1):
        current_prompt = prompt_plan[attempt - 1]
        current_quality = quality_plan[attempt - 1]
        last_prompt = current_prompt
        last_quality = current_quality
        payload = {
            "model": main_model,
            "input": current_prompt,
            "tools": [{"type": "image_generation", "model": image_model, "size": size, "quality": current_quality, "output_format": output_format}],
            "stream": False,
        }
        try:
            session = requests.Session()
            # 閬垮厤绯荤粺浠ｇ悊鎶婃湰鍦扮敓鎴愯姹傝浆鍒伴敊璇?涓嶅彲鐢ㄧ殑浠ｇ悊閾捐矾銆?
            session.trust_env = False
            response = session.post(url, headers=headers, json=payload, timeout=timeout_seconds)
            response.raise_for_status()
            data = response.json()
            image_list = extract_image_base64_list(data)
            if not image_list:
                preview = json.dumps(data, ensure_ascii=False)[:1200]
                error_text = with_resolution_hint(f"鎺ュ彛鎴愬姛杩斿洖锛屼絾娌℃湁鍙栧埌鍥剧墖缁撴灉銆傝繑鍥為瑙堬細{preview}", size)
                return {"ok": False, "index": index, "prompt": current_prompt, "original_prompt": prompt, "files": [], "elapsed": round(time.time() - start, 2), "error": error_text, "error_type": classify_generation_error(error_text), "attempts": attempt, "request_url": url, "quality_used": current_quality}
            saved = []
            ext = output_format.lower().replace("jpg", "jpeg")
            prompt_stub = safe_name(current_prompt[:35])
            for img_i, img_b64 in enumerate(image_list, start=1):
                file_name = f"{stamp()}_{index:03d}_{img_i:02d}_{prompt_stub}.{ext}"
                file_path = save_dir / file_name
                file_path.write_bytes(base64.b64decode(img_b64))
                saved.append(str(file_path))
            return {"ok": True, "index": index, "prompt": current_prompt, "original_prompt": prompt, "files": saved, "elapsed": round(time.time() - start, 2), "error": "", "error_type": "", "response_id": data.get("id", ""), "attempts": attempt, "request_url": url, "quality_used": current_quality}
        except requests.exceptions.HTTPError as e:
            body = ""
            try:
                body = response.text[:1200]
            except Exception:
                pass
            status_code = getattr(getattr(e, "response", None), "status_code", None)
            last_error = with_resolution_hint(f"HTTPError: {e} | {body}", size)
            if status_code and status_code < 500:
                return {"ok": False, "index": index, "prompt": current_prompt, "original_prompt": prompt, "files": [], "elapsed": round(time.time() - start, 2), "error": last_error, "error_type": classify_generation_error(last_error), "attempts": attempt, "request_url": url, "quality_used": current_quality}
        except requests.exceptions.ProxyError as e:
            last_error = "浠ｇ悊杩炴帴澶辫触锛氱郴缁熶唬鐞嗘垨缃戠粶浠ｇ悊鏂紑浜嗘帴鍙ｈ姹傘€傜▼搴忓凡榛樿蹇界暐绯荤粺浠ｇ悊锛涘鏋滀粛澶辫触锛岃妫€鏌?VPN/浠ｇ悊銆侀槻鐏鎴?AinaibaHub 涓婃父銆傚師濮嬮敊璇細" + str(e)
        except requests.exceptions.ConnectionError as e:
            last_error = "缃戠粶杩炴帴澶辫触锛氭帴鍙ｆ湇鍔″櫒鎴栦腑闂寸綉缁滅洿鎺ユ柇寮€锛屾病鏈夎繑鍥?HTTP 鍝嶅簲銆傚父瑙佸師鍥狅細浠ｇ悊/VPN銆佺綉鍏?60 绉掕秴鏃躲€丄inaibaHub 涓婃父涓存椂鏂祦銆傚凡鑷姩灏濊瘯闄嶄綆 quality銆傚師濮嬮敊璇細" + str(e)
        except requests.exceptions.Timeout as e:
            last_error = f"璇锋眰瓒呮椂锛歿timeout_seconds} 绉掑唴娌℃湁瀹屾垚銆傚凡鑷姩灏濊瘯闄嶄綆 quality銆傚師濮嬮敊璇細{e}"
        except Exception as e:
            last_error = with_resolution_hint(str(e), size)
        if attempt < attempts:
            time.sleep(min(2 * attempt, 6))
    return {"ok": False, "index": index, "prompt": last_prompt, "original_prompt": prompt, "files": [], "elapsed": round(time.time() - start, 2), "error": last_error, "error_type": classify_generation_error(last_error), "attempts": attempts, "request_url": url, "quality_used": last_quality}


def copy_delivery_package(project: dict, images: List[dict], delivery_note: str) -> str:
    project_folder = Path(project["folder"])
    delivery_dir = project_folder / "delivery" / f"delivery_{stamp()}"
    delivery_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    count = 1
    for img in images:
        src = Path(img["file"])
        if not src.exists():
            continue
        ext = src.suffix or ".png"
        platform = safe_name(project.get("platform", "platform"), 20)
        product = safe_name(project.get("product_name", "product"), 30)
        dst = delivery_dir / f"{count:02d}_{platform}_{product}{ext}"
        shutil.copy2(src, dst)
        rows.append({"index": count, "file": str(dst), "source": str(src), "prompt": img.get("prompt", ""), "status": img.get("status", "")})
        count += 1
    note = [
        f"椤圭洰锛歿project_label(project)}",
        f"浜や粯鏃堕棿锛歿now_text()}",
        f"浜や粯鍥剧墖鏁帮細{len(rows)}",
        "",
        "浜や粯璇存槑锛?,
        delivery_note or "鏈氦浠樺寘鍖呭惈绛涢€夊悗鐨勪骇鍝佸浘绱犳潗锛岃鎸夊钩鍙拌姹傝嚜琛屾坊鍔犳枃瀛楀拰浠锋牸淇℃伅銆?,
        "",
        "鎻愮ず璇嶈褰曪細",
    ]
    for row in rows:
        note.append(f"{row['index']:02d}. {row.get('prompt', '')}")
    (delivery_dir / "浜や粯璇存槑.txt").write_text(NEWLINE.join(note), encoding="utf-8")
    save_csv(delivery_dir / "delivery_manifest.csv", rows)
    archive_base = str(delivery_dir)
    shutil.make_archive(archive_base, "zip", delivery_dir)
    return str(delivery_dir) + ".zip"


def read_uploaded_text(uploaded) -> str:
    raw = uploaded.read()
    for enc in ["utf-8", "utf-8-sig", "gbk", "gb18030"]:
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            pass
    return raw.decode("utf-8", errors="ignore")


def run_self_tests() -> None:
    import tempfile
    assert safe_name('a b/c:*?"<>|') == "a_b_c"
    assert "Taobao" in build_requirement_prompt("cup", "white ceramic", "Taobao", "main image", "1:1", "white background", "centered", "soft light", "no text", "premium", "sharp", ["no watermark"])
    assert len(extract_image_base64_list({"output": [{"type": "image_generation_call", "result": "abc"}]})) == 1
    assert len(extract_image_base64_list({"data": [{"b64_json": "abc"}, {"image_base64": "def"}]})) == 2
    with tempfile.TemporaryDirectory() as tmp:
        folder = make_project_folder(tmp, "瀹㈡埛 A", "淇濇俯鏉?, "娣樺疂")
        assert Path(folder).exists()
        manifest = [{"id": "1", "file": "a.png", "status": "鏈瓫閫?}]
        save_manifest(folder, manifest)
        assert load_manifest(folder)[0]["id"] == "1"
    print("self tests passed")


def check_runtime_dependencies() -> None:
    missing = []
    if not dependency_available("streamlit"):
        missing.append("streamlit")
    if not dependency_available("requests"):
        missing.append("requests")
    if missing:
        print("缂哄皯渚濊禆锛? + ", ".join(missing))
        print("璇峰湪浣犳湰鏈?PowerShell 閲岃繍琛岋細")
        print("pip install streamlit requests")
        print("鐒跺悗鍐嶈繍琛岋細")
        print("python -m streamlit run local_image_panel.py")
        raise SystemExit(1)


def main() -> None:
    check_runtime_dependencies()
    import streamlit as st

    st.set_page_config(page_title="AI 鐢靛晢瑙嗚鎺ュ崟宸ヤ綔鍙?, page_icon="馃柤锔?, layout="wide", initial_sidebar_state="expanded")

    if "prompts_text" not in st.session_state:
        st.session_state.prompts_text = ""
    if "results" not in st.session_state:
        st.session_state.results = []
    if "errors" not in st.session_state:
        st.session_state.errors = []
    if "last_batch_dir" not in st.session_state:
        st.session_state.last_batch_dir = ""
    if "api_key_memory" not in st.session_state:
        st.session_state.api_key_memory = os.getenv("XAI_API_KEY", "")

    with st.sidebar:
        st.title("璁剧疆")
        output_root = st.text_input("淇濆瓨鏍圭洰褰?, value=DEFAULT_ROOT, key="output_root_path_v2")
        root_path = ensure_dir(output_root)
        config = read_json(json_path(output_root, "config.json"), {})
        api_key = st.text_input("API Key", value=st.session_state.api_key_memory, type="password")
        st.session_state.api_key_memory = api_key
        raw_saved_base_url = config.get("base_url", DEFAULT_BASE_URL)
        saved_base_url = normalize_base_url(raw_saved_base_url)
        if saved_base_url != str(raw_saved_base_url or "").strip().rstrip("/"):
            st.warning("妫€娴嬪埌 Base URL 鏄敊璇煙鍚嶏紝宸叉仮澶嶄负 AinaibaHub銆傜偣淇濆瓨閰嶇疆鍚庡啓鍏ャ€?)
        base_url = st.text_input("Base URL", value=saved_base_url, key="sidebar_base_url_input")
        base_url = normalize_base_url(base_url)
        main_model = st.text_input("涓绘ā鍨?, value=config.get("main_model", DEFAULT_MAIN_MODEL))
        image_model = st.text_input("鍥惧儚妯″瀷", value=config.get("image_model", DEFAULT_IMAGE_MODEL))
        st.divider()
        resolution_level = st.selectbox("鍒嗚鲸鐜囩瓑绾?, RESOLUTION_LEVELS, index=0, key="sidebar_resolution_level_select")
        size = st.selectbox("灏哄", ["1024x1024", "1024x1536", "1536x1024"], index=0)
        effective_size = resolve_generation_size(resolution_level, size)
        if resolution_level != "鏍囧噯":
            st.caption(f"2K锛?048x2048 / 4K锛?840x3840锛涘綋鍓嶅皢鍚戞帴鍙ｈ姹?{effective_size}銆?)
        quality = st.selectbox("璐ㄩ噺", ["high", "medium", "low"], index=1, help="绋冲畾浼樺厛寤鸿 medium锛涘け璐ラ噸璇曚細鑷姩闄嶅埌 low銆?)
        output_format = st.selectbox("鏍煎紡", ["png", "jpeg", "webp"], index=0)
        parallel_workers = st.slider("鍚屾椂澶勭悊鏁伴噺", 1, 8, 1, help="鍥惧儚鐢熸垚瀹规槗琚綉鍏虫柇寮€锛屽缓璁厛鐢?1锛涚ǔ瀹氬悗鍐嶆彁楂樸€?)
        repeat_each_prompt = st.slider("姣忔潯鎻愮ず璇嶉噸澶嶇敓鎴愭鏁?, 1, 5, 1)
        timeout_seconds = st.slider("鍗曞紶瓒呮椂绉掓暟", 120, 900, 600, step=60)
        request_retries = st.slider("澶辫触鑷姩閲嶈瘯娆℃暟", 0, 3, 2, help="鍙缃戠粶鏂紑/涓婃父 5xx 绛変复鏃跺け璐ユ湁甯姪銆?)
        create_batch_folder = st.checkbox("姣忔鐢熸垚鍒涘缓鐙珛鎵规鏂囦欢澶?, value=True)
        st.divider()
        st.subheader("鏈湴鍚庡鐞?)
        export_mode = st.selectbox("瀵煎嚭娓呮櫚搴?, ["鍘熷浘", "楂樻竻2鍊?, "娴锋姤楂樻竻3000", "娴锋姤楂樻竻3840"], index=0)
        enable_text_layer = st.checkbox("鍚敤鏈湴鏂囧瓧灞?, value=False, help="AI 鍙敓鎴愬簳鍥撅紝鏈湴鐢?Pillow 鍙犲姞鐪熷疄涓枃銆?)
        poster_title = ""
        poster_subtitle = ""
        poster_tags = ""
        if enable_text_layer:
            poster_title = st.text_input("娴锋姤鏍囬", value="", key="sidebar_poster_title_input")
            poster_subtitle = st.text_area("娴锋姤鍓爣棰?, value="", height=70, key="sidebar_poster_subtitle_input")
            poster_tags = st.text_input("鏍囩锛岀敤閫楀彿鍒嗛殧", value="", key="sidebar_poster_tags_input")
            st.caption("褰撳墠妯℃澘锛氬乏鏍囬鍙宠瑙夈€傜暀绌哄垯鍙鍑烘棤鏂囧瓧搴曞浘锛涘缓璁彁绀鸿瘝鐢熸垚鏃犵湡瀹炴枃瀛楀簳鍥俱€?)
        if Image is None and (export_mode != "鍘熷浘" or enable_text_layer):
            st.warning("鏈畨瑁?Pillow锛屽悗澶勭悊涓嶅彲鐢ㄣ€傝杩愯锛歱ip install pillow")
        st.divider()
        col_a, col_b = st.columns(2)
        if col_a.button("淇濆瓨閰嶇疆", use_container_width=True):
            write_json(json_path(output_root, "config.json"), {"base_url": normalize_base_url(base_url), "main_model": main_model, "image_model": image_model})
            st.success("宸蹭繚瀛橀厤缃紝涓嶄繚瀛?API Key銆?)
        if col_b.button("鎵撳紑鐩綍", use_container_width=True, key="sidebar_open_root_dir_btn"):
            open_folder(output_root, st)
        if st.button("妫€娴嬫帴鍙ｈ繛閫氭€?, use_container_width=True, key="sidebar_check_api_connection_btn"):
            with st.spinner("姝ｅ湪妫€娴嬫帴鍙ｈ繛閫氭€?.."):
                diag = diagnose_api_connection(base_url)
            if diag.get("ok"):
                st.success(diag.get("message"))
            else:
                st.error(diag.get("message"))
            st.json(diag)
        if st.button("鎵撳紑鏈€杩戞壒娆?, use_container_width=True, key="sidebar_open_last_batch_btn"): 
            if st.session_state.last_batch_dir:
                open_folder(st.session_state.last_batch_dir, st)
            else:
                st.info("鏆傛棤鏈€杩戞壒娆°€?)

    projects = load_projects(output_root)
    customers = load_customers(output_root)
    project_options = {project_label(p): p.get("id") for p in projects}
    active_project_id = None
    active_project = None
    if project_options:
        chosen_project_label = st.sidebar.selectbox("褰撳墠椤圭洰", list(project_options.keys()))
        active_project_id = project_options[chosen_project_label]
        active_project = get_project_by_id(projects, active_project_id)

    st.title("AI 鐢靛晢瑙嗚鎺ュ崟宸ヤ綔鍙?)
    st.caption("鍥剧墖闇€姹傛爣鍑嗗寲锛屾彁绀鸿瘝鑷姩鐢熸垚锛屾壒閲忓嚭鍥撅紝鍥剧墖绛涢€夛紝浜や粯鍖呭鍑猴紝椤圭洰鍜屽鎴疯褰曘€?)

    stats_images = 0
    stats_delivery = 0
    for p in projects:
        manifest = load_manifest(p.get("folder", "")) if p.get("folder") else []
        stats_images += len(manifest)
        stats_delivery += len([x for x in manifest if x.get("status") == "浜や粯鍥?])

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("椤圭洰鏁?, len(projects))
    c2.metric("瀹㈡埛鏁?, len(customers))
    c3.metric("鐢熸垚鍥剧墖", stats_images)
    c4.metric("浜や粯鍊欓€?, stats_delivery)
    c5.metric("褰撳墠澶辫触", len(st.session_state.errors))

    tabs = st.tabs(["棣栭〉", "椤圭洰", "瀹㈡埛", "鍥剧墖闇€姹?, "鐢熸垚涓績", "绛涢€夎川妫€", "鍚庡鐞嗕氦浠?, "妯℃澘搴?, "妯℃澘閲囬泦", "鍙傝€冨浘", "鍘嗗彶閲嶈瘯", "璇濇湳搴?])

    with tabs[0]:
        st.subheader("宸ヤ綔鍙版€昏")
        st.write("寤鸿娴佺▼锛氭柊寤洪」鐩紝鐒跺悗鍒板浘鐗囬渶姹傜敓鎴愭彁绀鸿瘝锛屽啀鍒扮敓鎴愪腑蹇冩壒閲忓嚭鍥撅紝鏈€鍚庡湪绛涢€夎川妫€閲屾爣璁颁氦浠樺浘銆?)
        if active_project:
            st.success(f"褰撳墠椤圭洰锛歿project_label(active_project)}")
            st.code(active_project.get("folder", ""), language=None)
        else:
            st.warning("杩樻病鏈夐」鐩紝鍏堝幓 椤圭洰 椤垫柊寤恒€?)
        st.markdown("### 杩涜涓」鐩?)
        for p in projects[-10:][::-1]:
            st.write(f"{p.get('created_at')} | {project_label(p)} | 鎶ヤ环 {p.get('quote', '')} | 鎴 {p.get('deadline', '')}")

    with tabs[1]:
        st.subheader("椤圭洰绠＄悊")

        with st.expander("鏂板缓椤圭洰", expanded=not bool(projects)):
            nc1, nc2 = st.columns(2)
            customer_name = nc1.text_input("瀹㈡埛鍚?, value="缁冧範瀹㈡埛", key="new_project_customer_name")
            product_name = nc2.text_input("浜у搧鍚?, value="榛戣壊涓嶉攬閽繚娓╂澂", key="new_project_product_name")
            platform = nc1.selectbox("骞冲彴", PLATFORMS, index=0, key="new_project_platform")
            use_case = nc2.selectbox("鐢ㄩ€?, USE_CASES, index=7, key="new_project_use_case")
            deadline = nc1.text_input("鎴鏃堕棿", value="", key="new_project_deadline")
            quote = nc2.number_input("鎶ヤ环", min_value=0.0, value=0.0, step=10.0, key="new_project_quote")
            project_notes = st.text_area("椤圭洰澶囨敞", height=80, key="new_project_notes")

            if st.button("鍒涘缓椤圭洰", type="primary", use_container_width=True, key="create_project_btn"):
                folder = make_project_folder(output_root, customer_name, product_name, platform)
                project = {
                    "id": uid(),
                    "created_at": now_text(),
                    "customer_name": customer_name,
                    "product_name": product_name,
                    "platform": platform,
                    "use_case": use_case,
                    "status": "寰呭紑濮?,
                    "deadline": deadline,
                    "quote": quote,
                    "paid": 0.0,
                    "notes": project_notes,
                    "folder": folder,
                }
                projects.append(project)
                save_projects(output_root, projects)

                if not any(c.get("name") == customer_name for c in customers):
                    customers.append(
                        {
                            "id": uid(),
                            "name": customer_name,
                            "contact": "",
                            "source": platform,
                            "tags": [],
                            "notes": "",
                            "created_at": now_text(),
                        }
                    )
                    save_customers(output_root, customers)

                st.success("椤圭洰宸插垱寤恒€?)
                st.rerun()

        st.markdown("### 椤圭洰鍒楄〃")
        for project in projects[::-1]:
            with st.expander(project_label(project)):
                cols = st.columns(4)
                status_index = PROJECT_STATUS.index(project.get("status", "寰呭紑濮?)) if project.get("status") in PROJECT_STATUS else 0
                new_status = cols[0].selectbox("鐘舵€?, PROJECT_STATUS, index=status_index, key="status_" + project["id"])
                new_paid = cols[1].number_input("瀹炴敹", min_value=0.0, value=float(project.get("paid", 0.0)), step=10.0, key="paid_" + project["id"])
                cols[2].write(f"鎶ヤ环锛歿project.get('quote', '')}")
                cols[3].write(f"鎴锛歿project.get('deadline', '')}")
                st.code(project.get("folder", ""), language=None)
                new_notes = st.text_area("澶囨敞", value=project.get("notes", ""), key="notes_" + project["id"])

                u1, u2 = st.columns(2)
                if u1.button("淇濆瓨椤圭洰淇敼", key="save_" + project["id"], use_container_width=True):
                    project["status"] = new_status
                    project["paid"] = new_paid
                    project["notes"] = new_notes
                    save_projects(output_root, projects)
                    st.success("宸蹭繚瀛樸€?)

                if u2.button("鎵撳紑椤圭洰鏂囦欢澶?, key="open_" + project["id"], use_container_width=True):
                    open_folder(project.get("folder", output_root))

    with tabs[2]:
        st.subheader("瀹㈡埛绠＄悊")
        with st.expander("鏂板瀹㈡埛"):
            cn1, cn2 = st.columns(2)
            name = cn1.text_input("瀹㈡埛鍚嶇О")
            contact = cn2.text_input("鑱旂郴鏂瑰紡")
            source = cn1.selectbox("鏉ユ簮", PLATFORMS, key="new_customer_source")
            tag_choice = cn2.multiselect("瀹㈡埛鏍囩", CUSTOMER_TAGS)
            notes = st.text_area("瀹㈡埛澶囨敞")
            if st.button("淇濆瓨瀹㈡埛", use_container_width=True, key="save_customer_btn"):
                if name.strip():
                    customers.append({"id": uid(), "name": name, "contact": contact, "source": source, "tags": tag_choice, "notes": notes, "created_at": now_text()})
                    save_customers(output_root, customers)
                    st.success("宸蹭繚瀛樺鎴枫€?)
                    st.rerun()
        for c in customers[::-1]:
            with st.expander(c.get("name", "鏈懡鍚嶅鎴?)):
                st.write(f"鑱旂郴鏂瑰紡锛歿c.get('contact', '')}")
                st.write(f"鏉ユ簮锛歿c.get('source', '')}")
                st.write(f"鏍囩锛歿', '.join(c.get('tags', []))}")
                st.write(c.get("notes", ""))

    with tabs[3]:
        st.subheader("鍥剧墖闇€姹備腑蹇?)
        st.write("杩欓噷鍏堟妸鍥剧墖瑕佹眰鏍囧噯鍖栵紝鍐嶈嚜鍔ㄧ敓鎴愪笓涓氭彁绀鸿瘝銆?)
        rq1, rq2 = st.columns(2)
        product_name = rq1.text_input("浜у搧鍚嶇О", value=active_project.get("product_name", "榛戣壊涓嶉攬閽繚娓╂澂") if active_project else "榛戣壊涓嶉攬閽繚娓╂澂")
        example_key = rq2.selectbox("浜у搧绀轰緥", ["鑷畾涔?] + list(PRODUCT_EXAMPLES.keys()), key="req_product_example")
        default_desc = PRODUCT_EXAMPLES.get(example_key, "")
        product_desc = st.text_area("浜у搧鑻辨枃鎻忚堪锛岃秺鍏蜂綋瓒婂ソ", value=default_desc or "a matte black stainless steel insulated water bottle, modern shape, realistic metal texture", height=80)
        r1, r2, r3 = st.columns(3)
        platform_req = r1.selectbox("骞冲彴", PLATFORMS, index=0, key="req_platform")
        use_case_req = r2.selectbox("鐢ㄩ€?, USE_CASES, index=0, key="req_use_case")
        aspect_req = r3.selectbox("姣斾緥", ASPECT_HINTS, index=0, key="req_aspect")
        r4, r5, r6 = st.columns(3)
        background_req = r4.selectbox("鑳屾櫙", BACKGROUND_OPTIONS, key="req_background")
        composition_req = r5.selectbox("鏋勫浘", COMPOSITION_OPTIONS, key="req_composition")
        light_req = r6.selectbox("鍏夊奖", LIGHT_OPTIONS, key="req_light")
        r7, r8 = st.columns(2)
        text_policy = r7.selectbox("鏂囧瓧绛栫暐", TEXT_POLICIES, key="req_text_policy")
        style_name = r8.selectbox("椋庢牸", list(STYLE_PRESETS.keys()), key="req_style")
        extra_req = st.text_input("棰濆瑕佹眰", value="realistic product material, sharp focus, clean composition, professional advertising photography")
        bans = st.multiselect("绂佹椤?, BANNED_DEFAULT, default=BANNED_DEFAULT)
        if st.button("鐢熸垚鍥剧墖鏍囧噯鎻愮ず璇?, type="primary", use_container_width=True, key="build_requirement_prompt_btn"):
            prompt = build_requirement_prompt(product_name, product_desc, platform_req, use_case_req, aspect_req, background_req, composition_req, light_req, text_policy, STYLE_PRESETS[style_name], extra_req, bans)
            st.session_state.prompts_text = prompt
            st.success("宸茬敓鎴愶紝骞舵斁鍏ョ敓鎴愪腑蹇冦€?)
            st.code(prompt, language="text")

        st.markdown("### 涓€閿鍦烘櫙鍖?)
        selected_scenes = st.multiselect("閫夋嫨鍦烘櫙", list(SCENE_TEMPLATES.keys()), default=["鐧藉簳涓诲浘", "楂樼骇鎽勫奖妫?, "鍔炲叕妗屽満鏅?, "鎴峰闇茶惀", "娓呯埥鍐版劅", "绀煎搧閫佺ぜ", "灏忕孩涔︾鑽?, "鎶栭煶灏侀潰"], key="req_selected_scenes")
        if st.button("鐢熸垚澶氬満鏅彁绀鸿瘝鍖?, use_container_width=True, key="build_scene_prompt_pack_btn"):
            prompts = [build_scene_prompt(product_name, product_desc, scene, style_name, extra_req) for scene in selected_scenes]
            st.session_state.prompts_text = NEWLINE.join(prompts)
            st.success(f"宸茬敓鎴?{len(prompts)} 鏉℃彁绀鸿瘝锛屾斁鍏ョ敓鎴愪腑蹇冦€?)
            st.code(st.session_state.prompts_text, language="text")

    with tabs[4]:
        st.subheader("鐢熸垚涓績")
        uploaded_txt = st.file_uploader("瀵煎叆 txt 鎻愮ず璇?, type=["txt"], key="generate_txt_uploader")
        if uploaded_txt is not None:
            st.session_state.prompts_text = read_uploaded_text(uploaded_txt)
            st.success("宸插鍏ユ彁绀鸿瘝銆?)
        mode_col, complexity_col = st.columns(2)
        generation_mode = mode_col.selectbox("鐢熸垚妯″紡", COMMERCIAL_GENERATION_MODES, index=1, key="generation_mode_select")
        prompt_complexity = complexity_col.selectbox("Prompt澶嶆潅搴?, PROMPT_COMPLEXITIES, index=1, key="prompt_complexity_select")
        preset_cols = st.columns(5)
        for preset_idx, preset_name in enumerate(PROMPT_PRESETS.keys()):
            if preset_cols[preset_idx].button(preset_name, use_container_width=True, key=f"prompt_preset_{preset_idx}"):
                st.session_state.prompts_text = PROMPT_PRESETS[preset_name]
                st.rerun()
        st.text_area("鎻愮ず璇嶏紝涓€琛屼竴寮犲浘", key="prompts_text", height=260)
        raw_prompt_lines = [x.strip() for x in st.session_state.prompts_text.splitlines() if x.strip()]
        prompt_max_chars = st.slider("瀹為檯鍙戦€?Prompt 鏈€澶ч暱搴?, 300, 900, 520, 20, help="AinaibaHub 鍥惧儚閾捐矾瀵归暱 Prompt 鏁忔劅锛涚ǔ瀹氱敓浜у缓璁?420-520銆?)
        prompt_lines = [build_commercial_prompt(x, generation_mode, prompt_complexity, prompt_max_chars) for x in raw_prompt_lines]
        with st.expander("鏌ョ湅瀹為檯鍙戦€?Prompt"):
            for idx, actual_prompt in enumerate(prompt_lines, start=1):
                st.caption(f"绗?{idx} 鏉★紝{len(actual_prompt)} 瀛楃")
                st.code(actual_prompt, language="text")
        total_tasks = len(prompt_lines) * repeat_each_prompt
        st.info(f"鎻愮ず璇?{len(prompt_lines)} 鏉★紝姣忔潯閲嶅 {repeat_each_prompt} 娆★紝棰勮浠诲姟 {total_tasks} 涓€傛ā寮忥細{generation_mode}锛屽鏉傚害锛歿prompt_complexity}锛屽彂閫侀暱搴︿笂闄愶細{prompt_max_chars}銆?)
        g1, g2, g3, g4 = st.columns(4)
        start_gen = g1.button("寮€濮嬬敓鎴?, type="primary", use_container_width=True)
        if g2.button("娓呯┖鎻愮ず璇?, use_container_width=True, key="generate_clear_prompts_btn"):
            st.session_state.prompts_text = ""
            st.rerun()
        if g3.button("鎵撳紑杈撳嚭鐩綍", use_container_width=True, key="generate_open_output_dir_btn"):
            open_folder(output_root, st)
        if g4.button("娓呯┖褰撳墠缁撴灉", use_container_width=True, key="generate_clear_results_btn"):
            st.session_state.results = []
            st.session_state.errors = []
            st.rerun()

        if start_gen:
            base_url_for_generation = normalize_base_url(base_url)
            if base_url_for_generation != DEFAULT_BASE_URL:
                st.warning("Base URL 宸茶嚜鍔ㄤ慨姝ｄ负 AinaibaHub銆?)
            if not api_key.strip():
                st.error("API Key 缂哄け锛氳鍏堝湪宸︿晶濉啓 AinaibaHub API Key锛屼笉浼氬彂璧疯姹傘€?)
            elif not prompt_lines:
                st.error("鍏堣緭鍏ユ彁绀鸿瘝銆?)
            elif resolution_level != "鏍囧噯":
                st.error("褰撳墠绋冲畾妯″紡涓嶈姹?2K/4K銆傝鎶婂垎杈ㄧ巼绛夌骇鏀逛负鈥滄爣鍑嗏€濓紝楂樻竻鐢?Pillow 鍚庡鐞嗗畬鎴愩€?)
            else:
                expanded_prompts = []
                for p in prompt_lines:
                    for _ in range(repeat_each_prompt):
                        expanded_prompts.append(p)
                if active_project:
                    base_save_dir = Path(active_project["folder"]) / "generated"
                else:
                    base_save_dir = root_path / "quick_generated"
                save_dir = base_save_dir / f"batch_{stamp()}" if create_batch_folder else base_save_dir
                save_dir.mkdir(parents=True, exist_ok=True)
                st.session_state.last_batch_dir = str(save_dir)
                (save_dir / "prompts.txt").write_text(NEWLINE.join(expanded_prompts), encoding="utf-8")
                st.session_state.results = []
                st.session_state.errors = []
                progress = st.progress(0)
                status_box = st.empty()
                started = time.time()
                batch_records = []
                with ThreadPoolExecutor(max_workers=parallel_workers) as executor:
                    futures = [executor.submit(generate_one, p, i, api_key.strip(), base_url_for_generation, main_model.strip(), image_model.strip(), effective_size, quality, output_format, save_dir, timeout_seconds, request_retries) for i, p in enumerate(expanded_prompts, start=1)]
                    done = 0
                    for future in as_completed(futures):
                        result = future.result()
                        done += 1
                        progress.progress(done / len(futures))
                        status_box.info(f"宸插畬鎴?{done}/{len(futures)}")
                        if result.get("ok"):
                            post_data = post_process_files(result.get("files", []), export_mode, enable_text_layer, poster_title, poster_subtitle, poster_tags)
                            result.update(post_data)
                            if post_data.get("postprocess_errors"):
                                for err_text in post_data.get("postprocess_errors", []):
                                    st.warning(err_text)
                        record = {"time": now_text(), "project_id": active_project.get("id") if active_project else "", "batch_dir": str(save_dir), "index": result.get("index"), "ok": result.get("ok"), "elapsed": result.get("elapsed"), "prompt": result.get("prompt"), "original_prompt": result.get("original_prompt", ""), "files": ";".join(result.get("files", [])), "text_files": ";".join(result.get("text_files", [])), "hd_files": ";".join(result.get("hd_files", [])), "final_files": ";".join(result.get("final_files", result.get("files", []))), "export_mode": export_mode, "text_layer": enable_text_layer, "generation_mode": generation_mode, "prompt_complexity": prompt_complexity, "attempts": result.get("attempts", ""), "quality_used": result.get("quality_used", ""), "error_type": result.get("error_type", ""), "error": result.get("error", "")}
                        batch_records.append(record)
                        append_jsonl(root_path / "_history.jsonl", record)
                        if result.get("ok"):
                            st.session_state.results.append(result)
                        else:
                            st.session_state.errors.append(result)
                            append_jsonl(root_path / "_errors.jsonl", record)
                save_csv(save_dir / "batch_summary.csv", batch_records)
                append_jsonl(save_dir / "batch_log.jsonl", {"records": batch_records})
                if active_project:
                    manifest = load_manifest(active_project["folder"])
                    for result in st.session_state.results:
                        original_files = result.get("files", [])
                        final_files = result.get("final_files", original_files)
                        text_files = result.get("text_files", [])
                        hd_files = result.get("hd_files", [])
                        for file_index, fp in enumerate(original_files):
                            final_fp = final_files[file_index] if file_index < len(final_files) else fp
                            text_fp = text_files[file_index] if file_index < len(text_files) else ""
                            hd_fp = hd_files[file_index] if file_index < len(hd_files) else ""
                            manifest.append({"id": uid(), "file": final_fp, "original_file": fp, "text_file": text_fp, "hd_file": hd_fp, "prompt": result.get("prompt", ""), "status": "鏈瓫閫?, "note": "", "created_at": now_text(), "batch_dir": str(save_dir), "export_mode": export_mode, "text_layer": enable_text_layer})
                    save_manifest(active_project["folder"], manifest)
                    active_project["status"] = "寰呯瓫閫?
                    save_projects(output_root, projects)
                if resolution_level != "鏍囧噯" and st.session_state.errors:
                    st.warning(UNSUPPORTED_RESOLUTION_MESSAGE)
                st.success(f"瀹屾垚锛氭垚鍔?{len(st.session_state.results)}锛屽け璐?{len(st.session_state.errors)}锛岃€楁椂 {round(time.time() - started, 2)} 绉掋€?)
                st.code(str(save_dir), language=None)

        if st.session_state.results:
            st.markdown("### 褰撳墠缁撴灉")
            for result in sorted(st.session_state.results, key=lambda x: x["index"]):
                with st.expander(f"绗?{result.get('index')} 鏉★紝鑰楁椂 {result.get('elapsed')} 绉?):
                    st.caption(result.get("prompt", ""))
                    files = result.get("final_files", result.get("files", []))
                    cols = st.columns(min(3, max(1, len(files))))
                    for i, fp in enumerate(files):
                        with cols[i % len(cols)]:
                            st.image(fp, use_container_width=True)
                            st.code(fp, language=None)
        if st.session_state.errors:
            st.markdown("### 褰撳墠澶辫触")
            for err in st.session_state.errors:
                error_type = err.get("error_type") or classify_generation_error(err.get("error", ""))
                st.error(f"{error_type}锛歿err.get('error')}")
                st.caption(f"灏濊瘯娆℃暟锛歿err.get('attempts', '')} | 鏈€缁堣川閲忥細{err.get('quality_used', '')} | 瀹為檯鍙戦€侊細{err.get('prompt', '')}")

    with tabs[5]:
        st.subheader("鍥剧墖绛涢€夊拰璐ㄦ")
        if not active_project:
            st.warning("鍏堥€夋嫨鎴栧垱寤轰竴涓」鐩€?)
        else:
            manifest = load_manifest(active_project["folder"])
            if not manifest:
                st.info("褰撳墠椤圭洰杩樻病鏈夌敓鎴愬浘鐗囥€?)
            else:
                filter_status = st.selectbox("绛涢€夌姸鎬?, ["鍏ㄩ儴"] + IMAGE_STATUS, key="filter_image_status")
                filtered = manifest if filter_status == "鍏ㄩ儴" else [x for x in manifest if x.get("status") == filter_status]
                st.info(f"褰撳墠鏄剧ず {len(filtered)} 寮犮€?)
                quality_check = ["浜у搧涓嶅彉褰?, "姣斾緥姝ｅ父", "鏉愯川鐪熷疄", "鑳屾櫙骞插噣", "娌℃湁涔辩爜鏂囧瓧", "閫傚悎鍚庢湡鍔犲瓧", "鍟嗕笟鎽勫奖鎰熷己"]
                for img in filtered:
                    with st.expander(f"{img.get('status', '鏈瓫閫?)} | {Path(img.get('file', '')).name}"):
                        file_path = img.get("file", "")
                        if Path(file_path).exists():
                            st.image(file_path, use_container_width=True)
                        st.caption(img.get("prompt", ""))
                        st.markdown("璐ㄦ娓呭崟锛? + " / ".join(quality_check))
                        new_status = st.radio("鏍囪", IMAGE_STATUS, index=IMAGE_STATUS.index(img.get("status", "鏈瓫閫?)) if img.get("status") in IMAGE_STATUS else 0, horizontal=True, key="status_img_" + img["id"])
                        new_note = st.text_input("绛涢€夊娉?, value=img.get("note", ""), key="note_img_" + img["id"])
                        col_s1, col_s2 = st.columns(2)
                        if col_s1.button("淇濆瓨鏍囪", key="save_img_" + img["id"], use_container_width=True):
                            for item in manifest:
                                if item.get("id") == img.get("id"):
                                    item["status"] = new_status
                                    item["note"] = new_note
                            save_manifest(active_project["folder"], manifest)
                            st.success("宸蹭繚瀛樻爣璁般€?)
                        if col_s2.button("鎵撳紑鎵€鍦ㄦ枃浠跺す", key="open_img_" + img["id"], use_container_width=True):
                            open_folder(str(Path(file_path).parent), st)

    with tabs[6]:
        st.subheader("鍚庡鐞嗗拰浜や粯")
        if not active_project:
            st.warning("鍏堥€夋嫨鎴栧垱寤轰竴涓」鐩€?)
        else:
            manifest = load_manifest(active_project["folder"])
            delivery_candidates = [x for x in manifest if x.get("status") in ["浜や粯鍥?, "鏀惰棌"]]
            st.info(f"鍙氦浠樺€欓€夛細{len(delivery_candidates)} 寮犮€傚缓璁彧鎶婃渶缁堝浘鏍囪涓?浜や粯鍥俱€?)
            delivery_note = st.text_area("浜や粯璇存槑", value="鏈氦浠樺寘鍖呭惈绛涢€夊悗鐨勪骇鍝佸浘绱犳潗銆傚缓璁悗缁湪 Canva銆丳S 鎴栫瀹氫腑娣诲姞涓枃鏍囬銆佷环鏍煎拰鍗栫偣鏂囧瓧銆?, height=100)
            if st.button("鐢熸垚浜や粯鍖?zip", type="primary", use_container_width=True, key="create_delivery_zip_btn"):
                selected = [x for x in manifest if x.get("status") == "浜や粯鍥?]
                if not selected:
                    st.error("娌℃湁鏍囪涓?浜や粯鍥?鐨勫浘鐗囥€?)
                else:
                    zip_path = copy_delivery_package(active_project, selected, delivery_note)
                    active_project["status"] = "寰呬氦浠?
                    save_projects(output_root, projects)
                    st.success("浜や粯鍖呭凡鐢熸垚銆?)
                    st.code(zip_path, language=None)
            for img in delivery_candidates:
                if Path(img.get("file", "")).exists():
                    st.image(img.get("file"), width=220)
                    st.caption(img.get("status") + " | " + img.get("prompt", "")[:120])

    with tabs[7]:
        st.subheader("妯℃澘搴擄細搴曞浘搴?+ 濂楁枃瀛?+ 楂樻竻瀵煎嚭")
        st.caption("鎻愬墠瀛樺簳鍥撅紝鎺ュ崟鏃堕€夋嫨妯℃澘銆佽緭鍏ユ枃瀛椼€佷竴閿鍑洪珮娓呮捣鎶ャ€?)
        template_rows = load_templates(output_root)
        template_root_dir = templates_dir(output_root)
        export_root_dir = template_exports_dir(output_root)

        import_col, filter_col = st.columns([1, 1])
        with import_col:
            st.markdown("### 瀵煎叆妯℃澘搴曞浘")
            template_upload = st.file_uploader("涓婁紶搴曞浘", type=["png", "jpg", "jpeg", "webp"], key="template_library_upload_file")
            tpl_name = st.text_input("妯℃澘鍚嶇О", value="宸ュ巶娴锋姤妯℃澘", key="template_library_import_name")
            tpl_industry = st.selectbox("琛屼笟", TEMPLATE_INDUSTRIES, key="template_library_import_industry")
            tpl_purpose = st.selectbox("鐢ㄩ€?, TEMPLATE_PURPOSES, key="template_library_import_purpose")
            tpl_style = st.selectbox("椋庢牸", TEMPLATE_STYLES, key="template_library_import_style")
            tpl_layout = st.selectbox("鐗堝紡", TEMPLATE_LAYOUTS, key="template_library_import_layout")
            tpl_platform = st.selectbox("閫傜敤骞冲彴", TEMPLATE_PLATFORMS, key="template_library_import_platform")
            tpl_ratio = st.selectbox("姣斾緥", TEMPLATE_RATIOS, key="template_library_import_ratio")
            tpl_remark = st.text_area("澶囨敞", height=70, key="template_library_import_remark")
            if st.button("淇濆瓨鍒版ā鏉垮簱", type="primary", use_container_width=True, key="template_library_save_uploaded_template"):
                if template_upload is None:
                    st.error("璇峰厛涓婁紶搴曞浘銆?)
                else:
                    ext = Path(template_upload.name).suffix.lower() or ".png"
                    template_id = uid()
                    file_path = template_root_dir / f"{stamp()}_{template_id}_{safe_name(tpl_name)}{ext}"
                    file_path.write_bytes(template_upload.read())
                    template_rows.append({"id": template_id, "name": tpl_name, "file": str(file_path), "industry": tpl_industry, "purpose": tpl_purpose, "style": tpl_style, "layout": tpl_layout, "platform": tpl_platform, "ratio": tpl_ratio, "remark": tpl_remark, "created_at": now_text()})
                    save_templates(output_root, template_rows)
                    st.success("妯℃澘宸蹭繚瀛樸€?)
                    st.rerun()

        with filter_col:
            st.markdown("### 绛涢€夋ā鏉?)
            filter_industry = st.selectbox("绛涢€夎涓?, ["鍏ㄩ儴"] + TEMPLATE_INDUSTRIES, key="template_library_filter_industry")
            filter_purpose = st.selectbox("绛涢€夌敤閫?, ["鍏ㄩ儴"] + TEMPLATE_PURPOSES, key="template_library_filter_purpose")
            filter_style = st.selectbox("绛涢€夐鏍?, ["鍏ㄩ儴"] + TEMPLATE_STYLES, key="template_library_filter_style")
            filter_layout = st.selectbox("绛涢€夌増寮?, ["鍏ㄩ儴"] + TEMPLATE_LAYOUTS, key="template_library_filter_layout")
            filter_platform = st.selectbox("绛涢€夊钩鍙?, ["鍏ㄩ儴"] + TEMPLATE_PLATFORMS, key="template_library_filter_platform")
            st.metric("妯℃澘鎬绘暟", len(template_rows))
            st.code(str(template_root_dir), language=None)
            st.code(str(templates_index_path(output_root)), language=None)

        st.markdown("### 搴撳瓨杩涘害")
        industry_counts = {industry: 0 for industry in TEMPLATE_INDUSTRIES}
        for row in template_rows:
            normalized_industry = normalize_template_industry(row.get("industry", ""))
            industry_counts[normalized_industry] = industry_counts.get(normalized_industry, 0) + 1
        progress_cols = st.columns(2)
        for idx, industry in enumerate(TEMPLATE_INDUSTRIES):
            current_count = industry_counts.get(industry, 0)
            target_count = TEMPLATE_INDUSTRY_TARGETS.get(industry, 0)
            with progress_cols[idx % 2]:
                if target_count > 0:
                    if current_count < target_count:
                        status_text = f"杩樺樊 {target_count - current_count} 寮?
                    elif current_count == target_count:
                        status_text = "宸茶揪鏍?
                    else:
                        status_text = f"宸茶秴鍑?{current_count - target_count} 寮?
                    st.write(f"{industry}锛歿current_count} / {target_count}锛寋status_text}")
                    st.progress(min(current_count / target_count, 1.0), text=f"{industry} 搴撳瓨杩涘害")
                else:
                    st.write(f"{industry}锛歿current_count} 寮?)

        def _template_match(row: dict) -> bool:
            normalized_industry = normalize_template_industry(row.get("industry", ""))
            return ((filter_industry == "鍏ㄩ儴" or normalized_industry == filter_industry) and (filter_purpose == "鍏ㄩ儴" or row.get("purpose") == filter_purpose) and (filter_style == "鍏ㄩ儴" or row.get("style") == filter_style) and (filter_layout == "鍏ㄩ儴" or row.get("layout") == filter_layout) and (filter_platform == "鍏ㄩ儴" or row.get("platform") == filter_platform))

        filtered_templates = [row for row in template_rows if _template_match(row)]
        st.markdown("### 妯℃澘鍒楄〃")
        if "selected_template_id" not in st.session_state:
            st.session_state.selected_template_id = ""
        list_col, work_col = st.columns([1.15, 1])

        with list_col:
            if not filtered_templates:
                st.info("鏆傛棤绗﹀悎鏉′欢鐨勬ā鏉裤€傚厛涓婁紶鍑犲紶鏃犳枃瀛楀簳鍥俱€?)
            for tpl in filtered_templates[::-1]:
                tpl_id = tpl.get("id", "")
                display_industry = normalize_template_industry(tpl.get("industry", ""))
                with st.expander(f"{tpl.get('name', '鏈懡鍚?)} | {display_industry} | {tpl.get('purpose', '')} | {tpl.get('platform', '')}"):
                    if Path(tpl.get("file", "")).exists():
                        st.image(tpl.get("file"), width=260)
                    else:
                        st.warning("妯℃澘鏂囦欢涓嶅瓨鍦ㄣ€?)
                    st.caption(f"椋庢牸锛歿tpl.get('style', '')} | 鐗堝紡锛歿tpl.get('layout', '')} | 姣斾緥锛歿tpl.get('ratio', '')}")
                    st.caption(tpl.get("remark", ""))
                    c_select, c_delete = st.columns(2)
                    if c_select.button("閫夋嫨姝ゆā鏉?, use_container_width=True, key=f"template_library_select_{tpl_id}"):
                        st.session_state.selected_template_id = tpl_id
                        st.success("宸查€夋嫨妯℃澘锛屽彸渚у彲濂楁枃瀛椼€?)
                    if c_delete.button("鍒犻櫎妯℃澘", use_container_width=True, key=f"template_library_delete_{tpl_id}"):
                        template_rows = [x for x in template_rows if x.get("id") != tpl_id]
                        save_templates(output_root, template_rows)
                        st.success("宸蹭粠绱㈠紩鍒犻櫎妯℃澘锛涙簮鍥剧墖鏂囦欢鏈己鍒跺垹闄ゃ€?)
                        if st.session_state.selected_template_id == tpl_id:
                            st.session_state.selected_template_id = ""
                        st.rerun()
                    with st.expander("缂栬緫淇℃伅"):
                        edit_name = st.text_input("妯℃澘鍚嶇О", value=tpl.get("name", ""), key=f"template_library_edit_name_{tpl_id}")
                        normalized_edit_industry = normalize_template_industry(tpl.get("industry", ""))
                        edit_industry = st.selectbox("琛屼笟", TEMPLATE_INDUSTRIES, index=TEMPLATE_INDUSTRIES.index(normalized_edit_industry) if normalized_edit_industry in TEMPLATE_INDUSTRIES else 0, key=f"template_library_edit_industry_{tpl_id}")
                        edit_purpose = st.selectbox("鐢ㄩ€?, TEMPLATE_PURPOSES, index=TEMPLATE_PURPOSES.index(tpl.get("purpose", TEMPLATE_PURPOSES[0])) if tpl.get("purpose") in TEMPLATE_PURPOSES else 0, key=f"template_library_edit_purpose_{tpl_id}")
                        edit_style = st.selectbox("椋庢牸", TEMPLATE_STYLES, index=TEMPLATE_STYLES.index(tpl.get("style", TEMPLATE_STYLES[0])) if tpl.get("style") in TEMPLATE_STYLES else 0, key=f"template_library_edit_style_{tpl_id}")
                        edit_layout = st.selectbox("鐗堝紡", TEMPLATE_LAYOUTS, index=TEMPLATE_LAYOUTS.index(tpl.get("layout", TEMPLATE_LAYOUTS[0])) if tpl.get("layout") in TEMPLATE_LAYOUTS else 0, key=f"template_library_edit_layout_{tpl_id}")
                        edit_platform = st.selectbox("閫傜敤骞冲彴", TEMPLATE_PLATFORMS, index=TEMPLATE_PLATFORMS.index(tpl.get("platform", TEMPLATE_PLATFORMS[0])) if tpl.get("platform") in TEMPLATE_PLATFORMS else 0, key=f"template_library_edit_platform_{tpl_id}")
                        edit_ratio = st.selectbox("姣斾緥", TEMPLATE_RATIOS, index=TEMPLATE_RATIOS.index(tpl.get("ratio", TEMPLATE_RATIOS[0])) if tpl.get("ratio") in TEMPLATE_RATIOS else 0, key=f"template_library_edit_ratio_{tpl_id}")
                        edit_remark = st.text_area("澶囨敞", value=tpl.get("remark", ""), height=70, key=f"template_library_edit_remark_{tpl_id}")
                        if st.button("淇濆瓨妯℃澘淇℃伅", use_container_width=True, key=f"template_library_save_edit_{tpl_id}"):
                            for item in template_rows:
                                if item.get("id") == tpl_id:
                                    item.update({"name": edit_name, "industry": edit_industry, "purpose": edit_purpose, "style": edit_style, "layout": edit_layout, "platform": edit_platform, "ratio": edit_ratio, "remark": edit_remark})
                                    break
                            save_templates(output_root, template_rows)
                            st.success("妯℃澘淇℃伅宸蹭繚瀛樸€?)
                            st.rerun()

        selected_template = get_project_by_id(template_rows, st.session_state.selected_template_id)
        with work_col:
            st.markdown("### 濂楁枃瀛椾笌楂樻竻瀵煎嚭")
            if not selected_template:
                st.info("鍏堝湪宸︿晶閫夋嫨涓€寮犳ā鏉裤€?)
            else:
                st.success(f"褰撳墠妯℃澘锛歿selected_template.get('name', '')}")
                if Path(selected_template.get("file", "")).exists():
                    st.image(selected_template.get("file"), use_container_width=True)
                text_title = st.text_input("鏍囬", value="宸ュ巶鐩翠緵 鍝佽川淇濋殰", key="template_library_text_title")
                text_subtitle = st.text_area("鍓爣棰?, value="婧愬ご宸ュ巶 路 鏀寔瀹氬埗 路 鎵归噺渚涜揣", height=70, key="template_library_text_subtitle")
                tag1 = st.text_input("鏍囩1", value="婧愬ご宸ュ巶", key="template_library_text_tag1")
                tag2 = st.text_input("鏍囩2", value="鏀寔瀹氬埗", key="template_library_text_tag2")
                tag3 = st.text_input("鏍囩3", value="蹇€熷彂璐?, key="template_library_text_tag3")
                point1 = st.text_input("鍗栫偣1", value="涓ラ€夊師鏂欙紝绋冲畾渚涜揣", key="template_library_text_point1")
                point2 = st.text_input("鍗栫偣2", value="鏀寔 LOGO / 鍖呰瀹氬埗", key="template_library_text_point2")
                point3 = st.text_input("鍗栫偣3", value="涓€浠朵唬鍙?/ 鎵瑰彂鍚堜綔", key="template_library_text_point3")
                text_cta = st.text_input("CTA", value="绔嬪嵆鍜ㄨ锛岃幏鍙栧伐鍘傛姤浠?, key="template_library_text_cta")
                text_contact = st.text_input("鑱旂郴鏂瑰紡", value="寰俊 / 鐢佃瘽锛氳濉啓", key="template_library_text_contact")
                text_brand = st.text_input("鍝佺墝鍚?, value="", key="template_library_text_brand")
                template_export_mode = st.selectbox("瀵煎嚭娓呮櫚搴?, ["鍘熷浘", "楂樻竻2鍊?, "娴锋姤楂樻竻3000", "娴锋姤楂樻竻3840"], index=1, key="template_library_export_mode")
                if st.button("涓€閿鏂囧瓧骞跺鍑?, type="primary", use_container_width=True, key="template_library_render_export_btn"):
                    if selected_template.get("layout") != "宸︽爣棰樺彸瑙嗚":
                        st.warning("褰撳墠鐗堟湰鍙敮鎸佸乏鏍囬鍙宠瑙夛紱浼氭寜宸︽爣棰樺彸瑙嗚妯℃澘瀵煎嚭銆?)
                    try:
                        tags = ",".join([x for x in [tag1, tag2, tag3] if x.strip()])
                        result = render_template_text_left_title(selected_template.get("file", ""), export_root_dir, text_title, text_subtitle, tags, [point1, point2, point3], text_cta, text_contact, text_brand, template_export_mode)
                        st.success("妯℃澘娴锋姤宸插鍑恒€?)
                        st.image(result.get("final_file"), use_container_width=True)
                        st.code(result.get("final_file"), language=None)
                        if result.get("text_file"):
                            st.caption("鏂囧瓧鐗?)
                            st.code(result.get("text_file"), language=None)
                        if result.get("hd_file"):
                            st.caption("楂樻竻鐗?)
                            st.code(result.get("hd_file"), language=None)
                    except Exception as e:
                        st.error(f"瀵煎嚭澶辫触锛歿e}")
                if st.button("鎵撳紑妯℃澘瀵煎嚭鐩綍", use_container_width=True, key="template_library_open_export_dir_btn"):
                    open_folder(str(export_root_dir), st)

    with tabs[8]:
        st.subheader("妯℃澘閲囬泦锛氱礌鏉愭潵婧?+ 鑷缓搴曞浘 Prompt")
        st.caption("杩欓噷鐩存帴鏀捐繘缃戦〉閲岀敤锛氱偣閾炬帴鎵惧彲鍟嗙敤搴曞浘锛屾垨澶嶅埗 Prompt 鍒扮敓鎴愪腑蹇冩壒閲忚嚜寤烘ā鏉裤€?)
        source_industry = st.selectbox("閫夋嫨璧涢亾", TEMPLATE_INDUSTRIES, key="template_sourcing_industry_select")
        source_rows = build_template_source_rows(source_industry)
        target_count = TEMPLATE_INDUSTRY_TARGETS.get(source_industry, 0)
        st.info(f"{source_industry} 绗竴闃舵鐩爣锛歿target_count if target_count else '涓嶈鍥哄畾鐩爣'} 寮犲簳鍥俱€備紭鍏堟壘鏃犳枃瀛椼€佺暀鐧姐€佷骇鍝佸睍绀鸿儗鏅€?)

        source_tab, prompt_tab, rule_tab = st.tabs(["绱犳潗缃戠珯", "AI 鑷缓 Prompt", "鎺堟潈瑙勫垯"])
        with source_tab:
            st.markdown("### 鍙偣寮€鐨勭礌鏉愭悳绱㈤摼鎺?)
            for row in source_rows:
                with st.expander(f"{row['鏉ユ簮']} | {row['鍏抽敭璇?]}"):
                    st.write(f"绫诲瀷锛歿row['绫诲瀷']}")
                    st.link_button("鎵撳紑鎼滅储缁撴灉", row["鎼滅储閾炬帴"], use_container_width=True)
                    st.code(row["鎼滅储閾炬帴"], language=None)
                    st.caption(row["鎺堟潈澶囨敞"])
            if st.button("瀵煎嚭褰撳墠璧涢亾閲囬泦 CSV", use_container_width=True, key="template_sourcing_export_csv_btn"):
                sourcing_dir = ensure_dir(output_root) / "template_sourcing"
                sourcing_dir.mkdir(parents=True, exist_ok=True)
                csv_path = sourcing_dir / f"{safe_name(source_industry)}_template_sources.csv"
                save_csv(csv_path, source_rows)
                st.success("宸插鍑洪噰闆嗘竻鍗曘€?)
                st.code(str(csv_path), language=None)

        with prompt_tab:
            st.markdown("### 鍙洿鎺ュ鍒跺埌鐢熸垚涓績鐨勬棤鏂囧瓧搴曞浘 Prompt")
            prompt_count = st.number_input("鐢熸垚 Prompt 鏁伴噺", min_value=1, max_value=50, value=max(1, target_count or 10), step=1, key="template_sourcing_prompt_count")
            prompts = build_template_ai_prompts(source_industry, int(prompt_count))
            prompt_text = NEWLINE.join(prompts)
            st.text_area("鎵归噺 Prompt", value=prompt_text, height=420, key="template_sourcing_prompt_text_area")
            c_prompt_export, c_open_sourcing = st.columns(2)
            if c_prompt_export.button("瀵煎嚭 Prompt TXT", use_container_width=True, key="template_sourcing_export_prompts_btn"):
                sourcing_dir = ensure_dir(output_root) / "template_sourcing"
                sourcing_dir.mkdir(parents=True, exist_ok=True)
                prompt_path = sourcing_dir / f"{safe_name(source_industry)}_ai_prompts.txt"
                prompt_path.write_text(prompt_text, encoding="utf-8")
                st.success("宸插鍑?Prompt銆?)
                st.code(str(prompt_path), language=None)
            if c_open_sourcing.button("鎵撳紑閲囬泦鏂囦欢澶?, use_container_width=True, key="template_sourcing_open_folder_btn"):
                open_folder(str(ensure_dir(output_root) / "template_sourcing"), st)

        with rule_tab:
            st.markdown("### 鎺堟潈鍜岀瓫閫夎鍒?)
            st.write("1. 浼樺厛閫?no text / blank / background / product display锛屼笉瑕侀€夊甫澶ч噺鏂囧瓧鐨勫畬鏁存捣鎶ャ€?)
            st.write("2. 鍏嶈垂绔欎篃瑕佺湅 License锛涗汉鐗╄倴鍍忋€佸搧鐗?Logo銆佸晢鏍囦骇鍝佽璋ㄦ厧銆?)
            st.write("3. 浠樿垂妯℃澘涓嶈兘榛樿鎷挎潵杞崠锛屽繀椤荤‘璁ゅ彲鍟嗙敤銆佸彲浜屾敼銆佸彲浜や粯瀹㈡埛銆?)
            st.write("4. 鏈€绋宠矾绾匡細鍙傝€冪綉涓婄増寮忥紝鐢?AI 鑷缓鏃犳枃瀛楀簳鍥撅紝鍐嶆湰鍦板涓枃銆?)
            st.write("5. 涓嬭浇鍚庣殑绱犳潗瀵煎叆銆屾ā鏉垮簱銆嶏紝涓嶈鐩存帴瑕嗙洊婧愭枃浠躲€?)
            st.warning("閲嶇偣锛氳兘涓嬭浇涓嶇瓑浜庤兘鍗栥€備綘鐨勬ā鏉垮簱瑕佽褰曟潵婧愬拰鎺堟潈锛岄伩鍏嶅悗闈㈡帴鍗曠炕杞︺€?)

    with tabs[9]:
        st.subheader("鍙傝€冨浘鍜屽鎴峰師鍥?)
        st.warning("褰撳墠鍏堜繚瀛樺師鍥惧拰鐢熸垚鏀瑰浘闇€姹傝鏄庛€傜湡姝ｅ浘鐢熷浘鎴栧眬閮ㄦ敼鍥撅紝闇€瑕佸钩鍙版彁渚涘浘鐗囪緭鍏ユ帴鍙ｅ悗鍐嶆帴鍏ャ€?)
        if not active_project:
            st.info("寤鸿鍏堟柊寤洪」鐩啀涓婁紶瀹㈡埛鍘熷浘銆?)
        ref_file = st.file_uploader("涓婁紶瀹㈡埛鍘熷浘", type=["png", "jpg", "jpeg", "webp"], key="reference_image_uploader")
        ref_request = st.text_area("瀹㈡埛鏀瑰浘瑕佹眰", height=120, placeholder="渚嬪锛氫繚鎸佷骇鍝佷笉鍙橈紝鍙崲鎴愰珮绾ф憚褰辨鑳屾櫙锛屼笉瑕佹枃瀛楋紝閫傚悎娣樺疂涓诲浘銆?)
        if ref_file is not None:
            if active_project:
                ref_dir = Path(active_project["folder"]) / "reference"
            else:
                ref_dir = root_path / "reference"
            ref_dir.mkdir(parents=True, exist_ok=True)
            ref_path = ref_dir / f"{stamp()}_{safe_name(ref_file.name)}"
            ref_path.write_bytes(ref_file.read())
            st.success("鍙傝€冨浘宸蹭繚瀛樸€?)
            st.image(str(ref_path), use_container_width=True)
            st.code(str(ref_path), language=None)
        if st.button("鐢熸垚鏀瑰浘鎻愮ず璇嶅拰瀵规帴璇濇湳", use_container_width=True, key="build_reference_prompt_btn"):
            note = "Keep the original product shape, color, material, logo and packaging structure unchanged. Replace only the background and lighting with a premium commercial product photography scene. No text, no watermark, no logo distortion. Customer request: " + (ref_request.strip() or "upgrade the product image into a premium e-commerce product photo")
            st.code(note, language="text")
            st.code("璇锋彁渚?responses API 閲屼笂浼犲弬鑰冨浘鎴栧師鍥捐繘琛屽浘鐗囩紪杈戠殑瀹屾暣绀轰緥銆傝姹傦細淇濈暀涓讳綋銆佸彧鎹㈣儗鏅紝杩斿洖 base64 鎴?url锛學indows 鎴?Python 鍙繍琛屻€?, language="text")

    with tabs[10]:
        st.subheader("鍘嗗彶璁板綍鍜屽け璐ラ噸璇?)
        history = load_jsonl(root_path / "_history.jsonl", limit=200)
        errors = [x for x in history if not x.get("ok")]
        h1, h2, h3 = st.columns(3)
        if h1.button("澶辫触鎻愮ず璇嶆斁鍥炵敓鎴愪腑蹇?, use_container_width=True, key="history_retry_failed_prompts_btn"):
            st.session_state.prompts_text = NEWLINE.join([x.get("prompt", "") for x in errors if x.get("prompt")])
            st.success(f"宸叉斁鍏?{len(errors)} 鏉″け璐ユ彁绀鸿瘝銆?)
        if h2.button("瀵煎嚭鍘嗗彶 CSV", use_container_width=True, key="history_export_csv_btn"):
            csv_path = root_path / f"history_export_{stamp()}.csv"
            save_csv(csv_path, history)
            st.success(f"宸插鍑猴細{csv_path}")
        if h3.button("鎵撳紑杈撳嚭鐩綍", use_container_width=True, key="history_open_output_dir_btn"):
            open_folder(output_root, st)
        for row in history[:80]:
            label = "鎴愬姛" if row.get("ok") else "澶辫触"
            with st.expander(f"{row.get('time')} | {label} | 绗?{row.get('index')} 鏉?| {row.get('elapsed')} 绉?):
                st.caption(row.get("prompt", ""))
                display_files = row.get("final_files") or row.get("files")
                if display_files:
                    for fp in display_files.split(";"):
                        if fp and Path(fp).exists():
                            st.image(fp, width=220)
                        if fp:
                            st.code(fp, language=None)
                if row.get("error"):
                    st.error(row.get("error"))

    with tabs[11]:
        st.subheader("璇濇湳搴?)
        for title, content in PHRASES.items():
            with st.expander(title):
                st.code(content, language="text")
        st.markdown("### 鑷畾涔変复鏃惰瘽鏈?)
        purpose = st.text_input("鍦烘櫙", value="缁欏鎴疯В閲?AI 浜у搧鍥炬湇鍔?)
        custom = f"浣犲ソ锛屾垜杩欒竟涓昏鍋?AI 鐢靛晢浜у搧鍥惧崌绾э紝鍙互鏍规嵁浜у搧鐗圭偣鐢熸垚涓诲浘銆佸満鏅浘銆佸皝闈㈠浘鍜岃鎯呴〉绱犳潗銆傚墠鏈熷彲浠ュ厛鍋氫竴寮犳牱鍥剧‘璁ら鏍硷紝婊℃剰鍚庡啀鍋氭暣濂椼€傚綋鍓嶅満鏅細{purpose}"
        st.code(custom, language="text")

    st.caption("V3 Lite锛氬浘鐗囬渶姹傛爣鍑嗗寲锛岄」鐩鐞嗭紝瀹㈡埛璁板綍锛岀敓鎴愪腑蹇冿紝绛涢€夎川妫€锛屼氦浠樺寘瀵煎嚭锛屽弬鑰冨浘鍏ュ彛锛屽巻鍙查噸璇曪紝璇濇湳搴撱€?)


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        run_self_tests()
    else:
        main()

