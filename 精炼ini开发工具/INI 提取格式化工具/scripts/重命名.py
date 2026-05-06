import os
import configparser
import re
from pathlib import Path

def parse_ini_content(content):
    config = configparser.ConfigParser(allow_no_value=True, comment_prefixes=';', interpolation=None)
    config.optionxform = str
    config.read_string(content)
    return config

def detect_encoding(file_path):
    encodings = ['utf-8', 'gbk', 'gb2312', 'latin1']
    for enc in encodings:
        try:
            with open(file_path, 'r', encoding=enc) as f:
                f.read()
            return enc
        except UnicodeDecodeError:
            continue
    return 'latin1'

def load_ini(file_path):
    encoding = detect_encoding(file_path)
    with open(file_path, 'r', encoding=encoding) as f:
        content = f.read()
    return parse_ini_content(content)

def save_ini(config, output_path):
    with open(output_path, 'w', encoding='utf-8') as f:
        for section in config.sections():
            f.write(f"[{section}]\n")
            for key in config[section]:
                value = config[section][key]
                if value == '' or value is None:
                    f.write(f"{key}\n")
                else:
                    f.write(f"{key}={value}\n")
            f.write("\n")

def ask_prefix():
    prefix = input("请输入统一前缀（3位字母，默认DEF）: ").strip().upper()
    if not prefix:
        prefix = "DEF"
    if len(prefix) != 3 or not prefix.isalpha():
        print("前缀必须为3位字母，已使用默认值DEF")
        prefix = "DEF"
    return prefix

def ask_var_start():
    var_start = input("局部变量从几开始（默认50）: ").strip()
    if not var_start:
        return 50
    try:
        return int(var_start)
    except ValueError:
        print("无效输入，使用默认值50")
        return 50

def ask_tf_start():
    tf_start = input("特遣和脚本从多少开始（默认500）: ").strip()
    if not tf_start:
        return 500
    try:
        return int(tf_start)
    except ValueError:
        print("无效输入，使用默认值500")
        return 500

def extract_hex_suffix(old_id):
    try:
        suffix = old_id[-4:].upper()
        return suffix
    except:
        return None

def collect_tf_references(ini_data):
    ref_ids = set()
    for section in ['TaskForces', 'ScriptTypes', 'TeamTypes']:
        if section in ini_data.sections():
            for key in ini_data[section]:
                value = ini_data[section][key]
                if value.startswith('01'):
                    ref_ids.add(value)
    for section in ini_data.sections():
        if section.startswith('01'):
            ref_ids.add(section)
    for section in ini_data.sections():
        for key in ini_data[section]:
            value = ini_data[section][key]
            if isinstance(value, str) and value.startswith('01'):
                ref_ids.add(value)
    return sorted(ref_ids)

def build_mappings(ini_data, prefix, var_start, tf_start):
    mappings = {
        "trigger": {},
        "tag": {},
        "variable": {},
        "tf_ref": {},
        "content_section": {}
    }

    if 'Actions' in ini_data.sections():
        old_trigger_ids = [k for k in ini_data['Actions'].keys() if k.startswith('01')]
        old_trigger_ids_sorted = sorted(old_trigger_ids)
        for idx, old_id in enumerate(old_trigger_ids_sorted, start=1):
            mappings["trigger"][old_id] = f"{prefix}{idx:04d}"

    if 'Tags' in ini_data.sections():
        old_tag_ids = [k for k in ini_data['Tags'].keys() if k.startswith('01')]
        old_tag_ids_sorted = sorted(old_tag_ids)
        for old_tag_id in old_tag_ids_sorted:
            tag_value = ini_data['Tags'][old_tag_id]
            parts = tag_value.split(',')
            if len(parts) >= 3:
                trigger_id = parts[-1].strip()
                if trigger_id in mappings["trigger"]:
                    mappings["tag"][old_tag_id] = f"{mappings['trigger'][trigger_id]}_tag"

    if 'VariableNames' in ini_data.sections():
        var_ids = sorted(ini_data['VariableNames'].keys(), key=int)
        for idx, old_id in enumerate(var_ids, start=var_start):
            mappings["variable"][old_id] = str(idx)

    tf_ref_ids = collect_tf_references(ini_data)
    for old_id in tf_ref_ids:
        suffix = extract_hex_suffix(old_id)
        if suffix is not None:
            mappings["tf_ref"][old_id] = f"{prefix}{suffix}"
            mappings["content_section"][old_id] = f"{prefix}{suffix}"
        else:
            mappings["tf_ref"][old_id] = old_id
            mappings["content_section"][old_id] = old_id

    tf_section_keys = {}
    for section in ['TaskForces', 'ScriptTypes', 'TeamTypes']:
        if section in ini_data.sections():
            sorted_keys = sorted(ini_data[section].keys(), key=lambda x: int(x) if x.isdigit() else 0)
            for idx, old_key in enumerate(sorted_keys, start=tf_start):
                tf_section_keys[(section, old_key)] = str(idx)

    mappings["tf_section_keys"] = tf_section_keys

    return mappings

def replace_all_references(value, mappings):
    result = value
    for old_id in sorted(mappings["tf_ref"].keys(), key=len, reverse=True):
        new_id = mappings["tf_ref"][old_id]
        result = result.replace(old_id, new_id)
    for old_id in sorted(mappings["trigger"].keys(), key=len, reverse=True):
        new_id = mappings["trigger"][old_id]
        result = result.replace(old_id, new_id)
    for old_id in sorted(mappings["tag"].keys(), key=len, reverse=True):
        new_id = mappings["tag"][old_id]
        result = result.replace(old_id, new_id)
    return result

def apply_mappings(ini_data, mappings):
    result_config = configparser.ConfigParser(allow_no_value=True, comment_prefixes=';', interpolation=None)
    result_config.optionxform = str

    trigger_sections = ['Actions', 'Events', 'Triggers']
    tf_sections = ['TaskForces', 'ScriptTypes', 'TeamTypes']

    for section in ini_data.sections():
        if section in trigger_sections:
            result_config.add_section(section)
            for old_id in ini_data[section]:
                value = ini_data[section][old_id]
                new_id = mappings["trigger"].get(old_id, old_id)
                new_value = replace_all_references(value, mappings)
                result_config.set(section, new_id, new_value)

        elif section == 'Tags':
            result_config.add_section(section)
            for old_id in ini_data[section]:
                value = ini_data[section][old_id]
                new_id = mappings["tag"].get(old_id, old_id)
                new_value = replace_all_references(value, mappings)
                result_config.set(section, new_id, new_value)

        elif section == 'VariableNames':
            result_config.add_section(section)
            for old_id in ini_data[section]:
                value = ini_data[section][old_id]
                new_id = mappings["variable"].get(old_id, old_id)
                result_config.set(section, new_id, value)

        elif section in tf_sections:
            result_config.add_section(section)
            for old_id in ini_data[section]:
                value = ini_data[section][old_id]
                new_id = mappings["tf_section_keys"].get((section, old_id), old_id)
                new_value = mappings["tf_ref"].get(value, value)
                result_config.set(section, new_id, new_value)

        elif section in mappings["content_section"]:
            new_section = mappings["content_section"][section]
            result_config.add_section(new_section)
            for key in ini_data[section]:
                value = ini_data[section][key]
                new_value = mappings["tf_ref"].get(value, value)
                result_config.set(new_section, key, new_value)

        else:
            result_config.add_section(section)
            for key in ini_data[section]:
                value = ini_data[section][key]
                new_value = mappings["tf_ref"].get(value, value)
                result_config.set(section, key, new_value)

    return result_config

def rename_ini(input_file, prefix=None, var_start=None, tf_start=None):
    input_path = Path(input_file)
    if not input_path.exists():
        print(f"文件不存在: {input_file}")
        return

    ini_data = load_ini(input_path)

    if prefix is None:
        prefix = ask_prefix()
    if var_start is None:
        var_start = ask_var_start()
    if tf_start is None:
        tf_start = ask_tf_start()

    print(f"\n使用配置: 前缀={prefix}, 变量起始={var_start}, 特遣/脚本起始={tf_start}")

    mappings = build_mappings(ini_data, prefix, var_start, tf_start)

    result_config = apply_mappings(ini_data, mappings)

    output_path = input_path.parent / f"{input_path.stem}-重命名.ini"
    save_ini(result_config, output_path)

    print(f"重命名完成: {output_path}")
    return output_path, mappings

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        input_file = sys.argv[1]
        prefix = sys.argv[2] if len(sys.argv) > 2 else None
        var_start = int(sys.argv[3]) if len(sys.argv) > 3 else None
        tf_start = int(sys.argv[4]) if len(sys.argv) > 4 else None
        rename_ini(input_file, prefix, var_start, tf_start)
    else:
        input_file = input("请输入要处理的文件路径: ").strip().strip('"')
        rename_ini(input_file)
