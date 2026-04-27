"""
从各范式 js 里提取 VoiceGuide.show({...}) 数据 → guides-data.json

支持的字段:
- image (相对路径,如 'img/rules.webp')
- btnRegion { x,y,w,h } (百分比字符串去掉 %,变 float)
- buttonText
- steps: [{ region, subtitle }] — subtitle 用 \n 连接多句(对齐 classic editor 格式)
"""
import re, json, os, sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))

FILES = [
    ('paradigms/flanker/flanker.js',          'flanker'),
    ('paradigms/sart/sart.js',                'sart'),
    ('paradigms/nback/nback.js',              'nback'),
    ('paradigms/vstmb/vstmb.js',              'vstmb'),
    ('paradigms/tmt/tmt.js',                  'tmt'),
    ('paradigms/clock/clock.js',              'clock'),
    ('paradigms/rmet/rmet.js',                'rmet'),
    ('paradigms/visuospatial/visuospatial.js','visuospatial'),
]


def find_guide_blocks(src):
    """
    Find all guide-config object literals in src.
    A guide config is an object {} containing image + btnRegion + steps (at top level).
    Works for both inline VoiceGuide.show({...}) and variable configs like
    vstmbVoiceConfig = { Object: {...}, Color: {...} }.
    Strategy: find each `image:` literal, walk backward to the enclosing `{`,
    then extract the balanced block. Deduplicate by byte range.
    """
    blocks = []
    seen = set()
    for m in re.finditer(r"image:\s*['\"]([^'\"?]+\.(?:webp|png|jpg|jpeg))(?:\?[^'\"]*)?['\"]", src):
        img_pos = m.start()
        # Walk backward, balancing braces, until we find enclosing '{'
        depth = 0
        pos = img_pos - 1
        while pos >= 0:
            c = src[pos]
            if c == '}':
                depth += 1
            elif c == '{':
                if depth == 0:
                    break
                depth -= 1
            pos -= 1
        if pos < 0:
            continue
        brace_start = pos
        brace_end = find_balanced(src, brace_start, '{', '}')
        if brace_end < 0:
            continue
        # Verify it has btnRegion and steps at some level inside
        block = src[brace_start:brace_end+1]
        if 'btnRegion' not in block or 'steps' not in block:
            continue
        key = (brace_start, brace_end)
        if key in seen:
            continue
        seen.add(key)
        blocks.append(block)
    return blocks


def pct_to_num(s):
    return round(float(s.rstrip('%').strip()), 2)


def extract_field(block, name):
    """Extract a single literal string field (image, buttonText). Strips ?query for image-like fields."""
    m = re.search(rf"{name}:\s*['\"`]([^'\"`]+)['\"`]", block)
    if not m:
        return None
    v = m.group(1)
    if name == 'image':
        v = v.split('?', 1)[0]
    return v


def extract_region(text):
    """Parse { x: 'X%', y: 'Y%', w: 'W%', h: 'H%' } or with numeric values."""
    m = re.search(
        r"x:\s*['\"]?([\d.]+)%?['\"]?\s*,\s*y:\s*['\"]?([\d.]+)%?['\"]?\s*,\s*w:\s*['\"]?([\d.]+)%?['\"]?\s*,\s*h:\s*['\"]?([\d.]+)%?['\"]?",
        text,
    )
    if not m:
        return None
    return {
        'x': round(float(m.group(1)), 2),
        'y': round(float(m.group(2)), 2),
        'w': round(float(m.group(3)), 2),
        'h': round(float(m.group(4)), 2),
    }


def find_balanced(src, start, open_c='{', close_c='}'):
    """From position of open_c, return the index of matching close_c."""
    depth = 0
    pos = start
    in_str = None
    escape = False
    while pos < len(src):
        c = src[pos]
        if in_str:
            if escape:
                escape = False
            elif c == '\\':
                escape = True
            elif c == in_str:
                in_str = None
            pos += 1
            continue
        if c in ("'", '"', '`'):
            in_str = c
        elif c == open_c:
            depth += 1
        elif c == close_c:
            depth -= 1
            if depth == 0:
                return pos
        pos += 1
    return -1


def extract_steps(block):
    """
    Find steps: [ { region: {...}, lines: [...] }, ... ]
    Return list of { region, subtitle (\n-joined) }.
    """
    m = re.search(r'steps:\s*\[', block)
    if not m:
        return []
    start = m.end() - 1  # position of '['
    end = find_balanced(block, start, '[', ']')
    if end < 0:
        return []
    steps_text = block[start+1:end]

    steps = []
    # Each step is { region: {...}, lines: [...] }
    # Walk forward looking for top-level { at depth 0
    pos = 0
    depth = 0
    step_start = -1
    in_str = None
    escape = False
    while pos < len(steps_text):
        c = steps_text[pos]
        if in_str:
            if escape:
                escape = False
            elif c == '\\':
                escape = True
            elif c == in_str:
                in_str = None
            pos += 1
            continue
        if c in ("'", '"', '`'):
            in_str = c
        elif c == '{':
            if depth == 0:
                step_start = pos
            depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0 and step_start >= 0:
                step_text = steps_text[step_start:pos+1]
                parsed = parse_step(step_text)
                if parsed:
                    steps.append(parsed)
                step_start = -1
        pos += 1
    return steps


def parse_step(step_text):
    # 先尝试 regions: [ {x,y,w,h}, {x,y,w,h}, ... ] (新格式 — 多红框)
    regions = []
    regions_m = re.search(r"regions:\s*\[", step_text)
    if regions_m:
        arr_start = regions_m.end() - 1
        arr_end = find_balanced(step_text, arr_start, '[', ']')
        if arr_end > 0:
            arr_text = step_text[arr_start+1:arr_end]
            # 每个元素都是 { x:...,y:...,w:...,h:... }
            pos = 0
            depth = 0
            obj_start = -1
            while pos < len(arr_text):
                c = arr_text[pos]
                if c == '{':
                    if depth == 0:
                        obj_start = pos
                    depth += 1
                elif c == '}':
                    depth -= 1
                    if depth == 0 and obj_start >= 0:
                        r = extract_region(arr_text[obj_start+1:pos])
                        if r:
                            regions.append(r)
                        obj_start = -1
                pos += 1

    # 兼容旧格式: region: { x,y,w,h }
    if not regions:
        region_m = re.search(r"region:\s*\{", step_text)
        if region_m:
            region_start = region_m.end() - 1
            region_end = find_balanced(step_text, region_start, '{', '}')
            region_inner = step_text[region_start+1:region_end]
            r = extract_region(region_inner)
            if r:
                regions.append(r)

    if not regions:
        return None

    # lines: [ {audio, subtitle}, ... ]  OR just subtitle on step
    subs = []
    lines_m = re.search(r'lines:\s*\[', step_text)
    if lines_m:
        lines_start = lines_m.end() - 1
        lines_end = find_balanced(step_text, lines_start, '[', ']')
        lines_text = step_text[lines_start+1:lines_end]
        for sm in re.finditer(r"subtitle:\s*['\"]((?:\\.|[^'\"\\])*)['\"]", lines_text):
            subs.append(sm.group(1).replace("\\'", "'"))
        if not subs:
            for sm in re.finditer(r"subtitle:\s*'([^']*)'", lines_text):
                subs.append(sm.group(1))
    else:
        sm = re.search(r"subtitle:\s*'([^']*)'", step_text)
        if sm:
            subs.append(sm.group(1))

    # 向下兼容: 始终输出 region(第 1 个)+ regions(全部)
    return {
        'region': regions[0],
        'regions': regions,
        'subtitle': '\n'.join(subs),
    }


def main():
    data = {}
    for rel, paradigm in FILES:
        fp = os.path.join(ROOT, rel)
        if not os.path.isfile(fp):
            print(f"SKIP (not found): {rel}", file=sys.stderr)
            continue
        with open(fp, encoding='utf-8') as f:
            src = f.read()
        blocks = find_guide_blocks(src)
        guides = []
        for b in blocks:
            g = {
                'image':      extract_field(b, 'image'),
                'buttonText': extract_field(b, 'buttonText'),
            }
            # btnRegion
            bm = re.search(r'btnRegion:\s*\{', b)
            if bm:
                bstart = bm.end() - 1
                bend = find_balanced(b, bstart, '{', '}')
                g['btnRegion'] = extract_region(b[bstart+1:bend])
            else:
                g['btnRegion'] = None
            g['steps'] = extract_steps(b)
            # Auto-label by image filename (e.g. img/rules.webp → rules, img/block1.webp → block1)
            if g['image']:
                base = os.path.splitext(os.path.basename(g['image']))[0]
                g['label'] = base
                guides.append(g)
        data[paradigm] = guides
        print(f"  {paradigm}: {len(guides)} guide(s)", file=sys.stderr)

    out_path = os.path.join(os.path.dirname(__file__), 'guides-data.json')
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"\nwrote {out_path}", file=sys.stderr)
    # Also print summary
    for p, gs in data.items():
        for i, g in enumerate(gs):
            print(f"  {p}[{i}] {g['image']} → {len(g['steps'])} steps", file=sys.stderr)


if __name__ == '__main__':
    main()
