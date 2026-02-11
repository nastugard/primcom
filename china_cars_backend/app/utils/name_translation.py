from __future__ import annotations

import json
import pathlib
import re

_RE_HAS_ZH = re.compile(r"[\u4e00-\u9fff]")

# Базовый словарь брендов для офлайн-нормализации (можно расширять).
BRAND_MAP: dict[str, str] = {
    "宝马": "BMW",
    "奔驰": "Mercedes-Benz",
    "奥迪": "Audi",
    "保时捷": "Porsche",
    "路虎": "Land Rover",
    "捷豹": "Jaguar",
    "凯迪拉克": "Cadillac",
    "福特": "Ford",
    "大众": "Volkswagen",
    "丰田": "Toyota",
    "本田": "Honda",
    "日产": "Nissan",
    "马自达": "Mazda",
    "三菱": "Mitsubishi",
    "雷克萨斯": "Lexus",
    "讴歌": "Acura",
    "红旗": "Hongqi",
    "长安": "Changan",
    "吉利": "Geely",
    "比亚迪": "BYD",
    "奇瑞": "Chery",
    "哈弗": "Haval",
    "坦克": "Tank",
    "领克": "Lynk & Co",
    "蔚来": "NIO",
    "理想": "Li Auto",
    "小鹏": "XPeng",
    "极氪": "Zeekr",
    "仰望": "Yangwang",
    "小米汽车": "Xiaomi Auto",
    "特斯拉": "Tesla",
    "劳斯莱斯": "Rolls-Royce",
    "宾利": "Bentley",
    "法拉利": "Ferrari",
    "兰博基尼": "Lamborghini",
    "玛莎拉蒂": "Maserati",
    "阿斯顿·马丁": "Aston Martin",
    "英菲尼迪": "Infiniti",
    "沃尔沃": "Volvo",
    "斯巴鲁": "Subaru",
    "铃木": "Suzuki",
    "雪佛兰": "Chevrolet",
    "别克": "Buick",
    "克莱斯勒": "Chrysler",
    "道奇": "Dodge",
    "吉普": "Jeep",
    "MINI": "MINI",
    "标致": "Peugeot",
    "雪铁龙": "Citroen",
    "雷诺": "Renault",
    "斯柯达": "Skoda",
    "菲亚特": "Fiat",
    "起亚": "Kia",
    "现代": "Hyundai",
    "双龙": "SsangYong",
    "荣威": "Roewe",
    "名爵": "MG",
    "广汽传祺": "GAC Trumpchi",
    "一汽奔腾": "Bestune",
    "东风风神": "Aeolus",
    "东风风行": "Forthing",
    "东风启辰": "Venucia",
    "东风纳米": "Dongfeng Nammi",
    "宝骏": "Baojun",
    "五菱": "Wuling",
    "江淮": "JAC",
    "上汽大通MAXUS": "Maxus",
    "哪吒汽车": "Neta",
    "零跑": "Leapmotor",
    "深蓝汽车": "Deepal",
    "阿维塔": "Avatr",
    "银河": "Geely Galaxy",
    "岚图": "Voyah",
    "智己": "IM Motors",
    "问界": "AITO",
    "方程豹": "Fangchengbao",
    "欧拉": "ORA",
    "魏牌": "WEY",
    "腾势": "Denza",
    "北京汽车": "BAIC",
    "北京越野": "BAIC Off-road",
    "北京现代": "Beijing Hyundai",
    "北汽新能源": "BAIC EV",
    "海马": "Haima",
    "启辰": "Venucia",
    "捷途": "Jetour",
    "星途": "Exeed",
    "斯威": "SWM",
    "瑞驰新能源": "Ruichi EV",
    "中国重汽": "Sinotruk",
    "依维柯": "Iveco",
    "福田": "Foton",
    "长城": "Great Wall",
    "smart": "smart",
    "蔚来汽车": "NIO",
    "创维汽车": "Skyworth Auto",
    "恒润汽车": "Hengrun Auto",
    "飞凡汽车": "Rising Auto",
    "江汽集团": "JAC",
    "林肯大陆": "Lincoln",
    "奔腾小马": "Bestune",
    "北汽制造": "BAW",
}

# Частые модели/серии, чтобы снять самый заметный "китайский шум" в UI.
MODEL_MAP: dict[str, str] = {
    "揽胜运动": "Range Rover Sport",
    "大切诺基(进口)": "Grand Cherokee (Import)",
    "宝马5系新能源": "BMW 5 Series PHEV",
    "宝马M3": "BMW M3",
    "奥迪A7L": "Audi A7L",
    "奥迪A4(进口)": "Audi A4 (Import)",
    "保时捷718": "Porsche 718",
    "凯迪拉克CT5": "Cadillac CT5",
    "蔚来ES8": "NIO ES8",
    "长安UNI-V": "Changan UNI-V",
    "领克03": "Lynk & Co 03",
    "仰望U7": "Yangwang U7",
    "奔驰EQC": "Mercedes-Benz EQC",
    "宝马3系": "BMW 3 Series",
    "宝马5系": "BMW 5 Series",
    "宝马7系": "BMW 7 Series",
    "宝马X1": "BMW X1",
    "宝马X3": "BMW X3",
    "宝马X5": "BMW X5",
    "奔驰C级": "Mercedes-Benz C-Class",
    "奔驰E级": "Mercedes-Benz E-Class",
    "奔驰S级": "Mercedes-Benz S-Class",
    "奔驰GLC": "Mercedes-Benz GLC",
    "奔驰GLE": "Mercedes-Benz GLE",
    "奥迪A4L": "Audi A4L",
    "奥迪A6L": "Audi A6L",
    "奥迪Q3": "Audi Q3",
    "奥迪Q5L": "Audi Q5L",
    "奥迪Q7": "Audi Q7",
    "特斯拉Model 3": "Tesla Model 3",
    "特斯拉Model Y": "Tesla Model Y",
    "凯迪拉克XT5": "Cadillac XT5",
    "凯迪拉克XT6": "Cadillac XT6",
    "保时捷Macan": "Porsche Macan",
    "保时捷Cayenne": "Porsche Cayenne",
    "红旗H5": "Hongqi H5",
    "红旗H9": "Hongqi H9",
    "蔚来ES6": "NIO ES6",
    "蔚来ET5": "NIO ET5",
    "理想L7": "Li Auto L7",
    "理想L8": "Li Auto L8",
    "理想L9": "Li Auto L9",
    "小鹏P7": "XPeng P7",
    "小鹏G6": "XPeng G6",
    "极氪001": "Zeekr 001",
    "极氪009": "Zeekr 009",
    "问界M7": "AITO M7",
    "问界M9": "AITO M9",
    "坦克300": "Tank 300",
    "坦克500": "Tank 500",
    "哈弗H6": "Haval H6",
    "哈弗大狗": "Haval Big Dog",
    "领克01": "Lynk & Co 01",
    "领克05": "Lynk & Co 05",
    "领克09": "Lynk & Co 09",
    "比亚迪秦PLUS": "BYD Qin PLUS",
    "比亚迪汉": "BYD Han",
    "比亚迪唐": "BYD Tang",
    "比亚迪宋PLUS": "BYD Song PLUS",
    "比亚迪海豹": "BYD Seal",
    "哪吒S": "Neta S",
    "哪吒U": "Neta U",
    "零跑C11": "Leapmotor C11",
    "零跑C01": "Leapmotor C01",
    "深蓝SL03": "Deepal SL03",
    "深蓝S7": "Deepal S7",
    "阿维塔11": "Avatr 11",
    "欧拉好猫": "ORA Good Cat",
    "五菱宏光MINIEV": "Wuling Hongguang Mini EV",
    "奕跑": "Kia KX1",
    "纳米01": "Nammi 01",
    "瑞虎8 PRO新能源": "Chery Tiggo 8 PRO PHEV",
    "远景X6 PRO": "Geely Vision X6 PRO",
    "瑞风L5": "JAC Refine L5",
    "明锐 PRO": "Skoda Octavia PRO",
    "柯珞克": "Skoda Karoq",
    "柯米克": "Skoda Kamiq",
    "速派": "Skoda Superb",
    "探岳": "Volkswagen Tayron",
    "途岳": "Volkswagen Tharu",
    "探歌": "Volkswagen T-Roc",
    "瑞风A60": "JAC Refine A60",
    "飞凡F7": "Rising F7",
    "创维EV6": "Skyworth EV6",
    "恒润HRS1": "Hengrun HRS1",
    "V级（平行进口）": "V-Class (Import)",
    "威霆": "Vito",
    "小米YU7": "Xiaomi YU7",
    "2系": "2 Series",
    "1系": "1 Series",
    "炫彩马": "Colorful Pony",
    "与众": "Yuzhong",
}


def has_chinese(value: str | None) -> bool:
    if not value:
        return False
    return bool(_RE_HAS_ZH.search(value))


def normalize_by_dict(value: str | None, mapping: dict[str, str]) -> str | None:
    if not value:
        return value
    s = str(value).strip()
    if not s:
        return value
    if s in mapping:
        return mapping[s]
    # Мягкая замена по вхождению (для строк вроде "奔驰V级（平行进口）")
    out = s
    changed = False
    for zh, en in mapping.items():
        if zh in out:
            out = out.replace(zh, en)
            changed = True
    return out if changed else value


def load_cache(path: str) -> dict[str, str]:
    p = pathlib.Path(path)
    if not p.exists():
        return {}
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if not isinstance(raw, dict):
        return {}
    out: dict[str, str] = {}
    for k, v in raw.items():
        if isinstance(k, str) and isinstance(v, str) and k.strip() and v.strip():
            out[k] = v
    return out


def save_cache(path: str, data: dict[str, str]) -> None:
    p = pathlib.Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
