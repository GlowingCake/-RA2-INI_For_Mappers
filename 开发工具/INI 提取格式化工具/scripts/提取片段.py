import os
import configparser
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
DEFAULT_INI_PATH = SCRIPT_DIR.parent / "default.ini"
SKIP_SECTIONS = {
    "Header", "Preview", "PreviewPack", "Basic", "FA2spVersionControl",
    "Houses", "IsoMapPack5", "Lighting", "Map", "OverlayDataPack",
    "OverlayPack", "Digest"
}

def parse_ini_content(content):
    config = configparser.ConfigParser(allow_no_value=True, comment_prefixes=';', interpolation=None)
    config.optionxform = str
    config.read_string(content)
    return config

def sections_differ(default_config, source_config, section):
    if section not in source_config:
        return False
    if section not in default_config:
        return True
    diff_keys = []
    for key in source_config[section]:
        if key not in default_config[section]:
            diff_keys.append(key)
        elif source_config[section][key] != default_config[section][key]:
            diff_keys.append(key)
    for key in default_config[section]:
        if key not in source_config[section]:
            diff_keys.append(key)
    return len(diff_keys) > 0

def extract_different_keys(default_config, source_config, section):
    result = {}
    if section not in source_config:
        return result
    if section not in default_config:
        for key in source_config[section]:
            result[key] = source_config[section][key]
        return result
    for key in source_config[section]:
        if key not in default_config[section]:
            result[key] = source_config[section][key]
        elif source_config[section][key] != default_config[section][key]:
            result[key] = source_config[section][key]
    return result

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

def preprocess_ini_content(content):
    lines = content.split('\n')
    result_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped == '=' or stripped.startswith('='):
            continue
        result_lines.append(line)
    return '\n'.join(result_lines)

def extract_sections(input_file, default_ini_path=DEFAULT_INI_PATH):
    input_path = Path(input_file)
    if not input_path.exists():
        print(f"文件不存在: {input_file}")
        return

    source_encoding = detect_encoding(input_path)

    with open(default_ini_path, 'r', encoding='utf-8') as f:
        default_content = f.read()
    default_config = parse_ini_content(default_content)

    with open(input_path, 'r', encoding=source_encoding) as f:
        source_content = f.read()
    source_content = preprocess_ini_content(source_content)
    source_config = parse_ini_content(source_content)

    extracted_sections = {}
    new_sections_file = None

    for section in source_config.sections():
        if section in SKIP_SECTIONS:
            continue

        if section in default_config.sections():
            if sections_differ(default_config, source_config, section):
                diff_keys = extract_different_keys(default_config, source_config, section)
                if diff_keys:
                    extracted_sections[section] = diff_keys
        else:
            if new_sections_file is None:
                new_sections_file = input_path.parent / f"{input_path.stem}-片段.ini"
            extracted_sections[section] = dict(source_config[section])

    if extracted_sections:
        output_path = input_path.parent / f"{input_path.stem}-提取.ini"
        with open(output_path, 'w', encoding='utf-8') as f:
            for section in extracted_sections:
                f.write(f"[{section}]\n")
                for key in extracted_sections[section]:
                    value = extracted_sections[section][key]
                    if value == '' or value is None:
                        f.write(f"{key}\n")
                    else:
                        f.write(f"{key}={value}\n")
                f.write("\n")
        print(f"提取完成: {output_path}")

    if new_sections_file and new_sections_file.exists():
        print(f"新增片段已保存: {new_sections_file}")

    return extracted_sections, new_sections_file

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        input_file = sys.argv[1]
    else:
        input_file = input("请输入要处理的文件路径: ").strip().strip('"')
    extract_sections(input_file)
