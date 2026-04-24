import os
import re
import pandas as pd
import requests
from PIL import Image
from io import BytesIO 
import urllib.parse
import time
import sys

# ==========================================
# CONSTANTS & DEFAULTS
# ==========================================
OPERATION_MODE_RENAME_ONLY = 1
OPERATION_MODE_RESIZE = 2

DEFAULT_CONFIG = {
    "sourcefile": "Source.csv",
    "outputfolder": "Processed_Images",
    "targetwidth": 2560,
    "targetheight": 1707,
    "maxfilesizemb": 1.0, 
    "operationmode": OPERATION_MODE_RESIZE,
    "manualsizing": 0,          # 0 = Auto (Rules), 1 = Manual (Config)
    "propertytype": "MVC",      # MVC or LEGACY
    "optimizedsuffix": 0        # 1 = Always add 'Optimized', 0 = Do not add
}

# EXTENDED PROFESSIONAL MAPPING - UPDATED FOR ALL REQUESTED DOC TYPES
DOC_TYPE_MAPPING = {
    'PHOTO GALLERY': 'PG',
    'FLASH GALLERY': 'Flash',
    'FLASH/ HOMEPAGE SLIDER': 'Flash',
    'PROPERTY LOGO': 'log',
    'PROPERTY LOGO - EMAIL': 'log',
    'PROPERTY LOGO - BROCHURE': 'log',
    'ILS PROPERTY LOGO': 'log',
    'CONTENT EDITOR': 'CE',
    'COMMUNITY THUMBNAIL': 'thumbnail',
    'FLOOR PLAN': 'FP',
    'FLOORPLAN': 'FP',
    'SITE PLAN': 'SP',
    'UNIT VIDEO': 'UV',
    'VIRTUAL TOUR': 'VT',
    'AMENITY': 'AmenityImage',
    'AMENITY IMAGES': 'AmenityImage',
    'BACKGROUND': 'BG',
    'BACKGROUND IMAGE': 'BG',
    'TEMPLATE IMAGE': 'Template',
    'TEMPLATE IMAGES': 'Template',
    'BANNER': 'Banner',
    'BANNER IMAGE': 'Banner',
    'THEME LEFT IMAGE': 'LeftThemeImage',
    'THEME RIGHT IMAGE': 'RightThemeImage',
    'CORP SEARCH RESULTS BANNER': 'Banner',
    'FOOTER IMAGE': 'Footer',
    'FAVICON IMAGE': 'Favicon',
    'ITEMS OF INTEREST': 'IOI',
    'EMAIL ATTACHMENT': 'EmailAttach',
    'UNIT IMAGE': 'UnitImage',
    'RESIDENT APP LOGO IMAGE': 'AppLogo',
    'BUILDING SVG MAP': 'BuildingMap',
    'FLOOR SVG MAP': 'FloorMap'
}

# PROFESSIONAL MULTI-KEYWORD VALIDATION ENGINE
# Updated to require "whole" description or specific abbreviation to prevent accidental skipping.
SHORTHAND_CHECK = {
    'PG': ['pg', 'photogallery', 'photogallary','photo gallary','photo gallery'],
    'Flash': ['flashgallery', 'flash'],
    'log': ['propertylogo', 'logo', 'log'],
    'CE': ['contenteditor', 'ce'],
    'thumbnail': ['communitythumbnail', 'thumbnail', 'thumb'],
    'FP': ['floorplan', 'fp'],
    'SP': ['siteplan', 'sp'],
    'AmenityImage': ['amenityimages', 'amenityimage', 'amenityimg'],
    'BG': ['backgroundimage', 'background', 'bg'],
    'Template': ['templateimage', 'template'],
    'Banner': ['bannerimage', 'banner'],
    'LeftThemeImage': ['leftthemeimage', 'lefttheme'],
    'RightThemeImage': ['rightthemeimage', 'righttheme'],
    'Footer': ['footerimage', 'footer'],
    'Favicon': ['faviconimage', 'favicon'],
    'IOI': ['itemsofinterest', 'ioi'],
    'EmailAttach': ['emailattachment', 'emailattach'],
    'UnitImage': ['unitimage'],
    'AppLogo': ['residentapplogo', 'applogo'],
    'BuildingMap': ['buildingsvgmap', 'buildingmap', 'buildingsvg'],
    'FloorMap': ['floorsvgmap', 'floormap', 'floorsvg']
}

PRIMARY_DOMAIN = "www.rentcafe.com"
FALLBACK_DOMAINS = ["cdngeneral.rentcafe.com", "cdngeneralcf.rentcafe.com"]

def clean_key(text):
    return re.sub(r'[^a-z0-9]', '', str(text).lower())

def load_configuration():
    config_keys = {clean_key(k): k for k in DEFAULT_CONFIG.keys()}
    final_config = DEFAULT_CONFIG.copy()
    
    df = None
    if os.path.exists("Config.xlsx"):
        try:
            df = pd.read_excel("Config.xlsx", header=None)
            print("[SYSTEM] Config.xlsx detected.")
        except: pass
    if df is None and os.path.exists("Config.csv"):
        try:
            df = pd.read_csv("Config.csv", header=None)
            print("[SYSTEM] Config.csv detected.")
        except: pass

    if df is not None:
        for _, row in df.iterrows():
            if pd.isna(row[0]): continue
            raw_key = clean_key(row[0])
            if raw_key in config_keys:
                internal_key = config_keys[raw_key]
                try:
                    val = row[1]
                    if internal_key in ["operationmode", "manualsizing", "optimizedsuffix"]:
                        try:
                            val = int(float(val))
                        except:
                            val = 1 if str(val).lower() == 'yes' else 0
                    elif internal_key in ["targetwidth", "targetheight"]:
                        val = int(float(val))
                    elif internal_key == "maxfilesizemb":
                        val = float(val)
                    else:
                        val = str(val).strip()
                    final_config[internal_key] = val
                except: pass
    
    final_config["propertytype"] = final_config["propertytype"].upper()
    print("[SYSTEM] Configuration parameters initialized.")
    return final_config

def clean_string(text):
    text = str(text) 
    cleaned = re.sub(r'[^a-zA-Z0-9]', '_', text)
    cleaned = re.sub(r'_+', '_', cleaned) 
    return cleaned.strip('_')

def get_filename_from_url(url):
    try:
        path = urllib.parse.urlparse(url).path
        return os.path.basename(urllib.parse.unquote(path))
    except:
        return f"unknown_{int(time.time())}"

def get_doc_type_abbreviation(doc_type):
    cleaned_type = str(doc_type).strip().upper()
    return DOC_TYPE_MAPPING.get(cleaned_type, 'XX') 

def process_vertical_image(img):
    width, height = img.size
    crop_amount = int(height * 0.15)
    return img.crop((0, crop_amount, width, height - crop_amount))

def get_scaled_dimensions(img_w, img_h, target_w, target_h, downscale_only=True):
    ratio_w = target_w / img_w
    ratio_h = target_h / img_h
    scale = min(ratio_w, ratio_h)
    if downscale_only and scale >= 1.0:
        return img_w, img_h
    return int(img_w * scale), int(img_h * scale)

def get_target_box(itype, prop_type):
    try: itype = int(float(itype))
    except: return None, None
    if itype == 2: return 99999, 480
    if itype == 5: return 500, 350
    if itype == 6: return 350, 99999
    if itype == 40: return 99999, 1000
    if prop_type == 'LEGACY':
        if itype == 120: return 670, 480
        if itype == 1:   return 1024, 768
    else: # MVC
        if itype in [1, 120, 12, 10, 4, 13, 14, 15, 28]: return 2560, 1707
    return None, None

def compress_and_save(img, save_path, max_mb, format_type='JPEG'):
    max_bytes = int(max_mb * 1024 * 1024)
    img_byte_arr = BytesIO()
    if format_type == 'PNG':
        img.save(img_byte_arr, format='PNG', optimize=True)
    else:
        quality = 95
        while quality >= 10:
            img_byte_arr.seek(0)
            img_byte_arr.truncate(0)
            img.save(img_byte_arr, format='JPEG', quality=quality) 
            if img_byte_arr.tell() <= max_bytes: break 
            quality -= 5 
    with open(save_path, 'wb') as f:
        f.write(img_byte_arr.getbuffer())
    return img_byte_arr.tell() / (1024 * 1024)

def transform_p_code_url(url, hmy_id):
    return re.sub(r"/dmslivecafe/2/\d+/", f"/dmslivecafe/3/{hmy_id}/", url)

def safe_encode_url(url):
    parts = urllib.parse.urlsplit(url)
    encoded_path = urllib.parse.quote(parts.path)
    return urllib.parse.urlunsplit((parts.scheme, parts.netloc, encoded_path, parts.query, parts.fragment))

def main_logic():
    cfg = load_configuration()
    
    print("=" * 80)
    print("IMAGE PROCESSING ENGINE - ACTIVE CONFIGURATION")
    print("-" * 80)
    print(f"  > Source File         : {cfg['sourcefile']}")
    print(f"  > Output Directory    : {cfg['outputfolder']}")
    print(f"  > Property Category   : {cfg['propertytype']}")
    print(f"  > Max File Size Limit : {cfg['maxfilesizemb']} MB")
    print(f"  > Optimized Suffix    : {'YES' if cfg['optimizedsuffix'] == 1 else 'NO'}")
    print("=" * 80)

    source_file = cfg["sourcefile"]
    output_folder = cfg["outputfolder"]
    manual_sizing = (cfg["manualsizing"] == 1)
    prop_type = cfg["propertytype"] 
    is_resize_mode = (cfg["operationmode"] == OPERATION_MODE_RESIZE)
    max_mb = cfg["maxfilesizemb"]
    add_opt_suffix = (cfg["optimizedsuffix"] == 1)
    
    hmy_lookup = {}
    if os.path.exists("PropertyHMY.csv"):
        try:
            pdf = pd.read_csv("PropertyHMY.csv")
            # Clean column names: remove whitespace and make case-insensitive if needed
            pdf.columns = [c.strip() for c in pdf.columns]
            cols = pdf.columns

            # Determine which column name exists for Code and Id
            code_col = next((c for c in ["Propery Code", "Property Code"] if c in cols), None)
            id_col = next((c for c in ["Propery Id", "Property Id"] if c in cols), None)

            if code_col and id_col:
                for _, r in pdf.iterrows():
                    # Convert to string and strip values to ensure clean lookup keys
                    key = str(r[code_col]).strip()
                    val = str(r[id_col]).strip()
                    hmy_lookup[key] = val
                
                print(f"[INFO] Loaded {len(hmy_lookup)} HMY mappings using columns: '{code_col}' and '{id_col}'.")
            else:
                print("[ERROR] Could not find valid Property Code or ID columns.")
                
        except Exception as e:
            print(f"[ERROR] Failed to load HMY mappings: {e}")
        if not os.path.exists(source_file):
            print(f"ERROR: {source_file} not found."); return

    try:
        try: df = pd.read_csv(source_file, encoding='utf-8-sig', header=None, engine='python')
        except: df = pd.read_csv(source_file, encoding='latin-1', header=None, engine='python')
        df.columns = [str(c).strip() for c in df.iloc[0]]
        df = df.iloc[1:].copy()
        df.insert(0, 'RowIdx', df.index + 2)
    except Exception as e:
        print(f"CSV Error: {e}"); return

    if not os.path.exists(output_folder): os.makedirs(output_folder)

    session = requests.Session()
    session.headers.update({'User-Agent': 'Mozilla/5.0'})
    failed_records = []
    process_log = []

    for _, row in df.iterrows():
        row_idx = row['RowIdx']
        orig_prop = str(row.get('Property/Company Code', row.get('Property Code', ''))).strip()
        target_prop = str(row.get('Target Property', '')).strip()
        if not target_prop or target_prop.lower() == 'nan': target_prop = orig_prop
            
        orig_file_name = row.get('File Name', 'Unknown')
        base_log = f"Row {row_idx:03} | {{status}} | {orig_prop} -> {target_prop} | {orig_file_name}"

        if str(row.get('Active/Inactive', '')).upper() == 'INACTIVE':
            print(f"[{base_log.format(status='SKIP')}] Inactive record.")
            continue

        try:
            clean_orig = clean_string(orig_prop)
            clean_target = clean_string(target_prop)
            doc_type_val = str(row.get('Doc. Type', 'Unknown')).strip()
            
            target_subfolder = os.path.join(output_folder, f"{clean_target}__{clean_string(doc_type_val)}")
            if not os.path.exists(target_subfolder): os.makedirs(target_subfolder)

            raw_url = str(row['Full Path']).strip()
            encoded_url = safe_encode_url(raw_url)
            
            urls = [encoded_url]
            if orig_prop.lower().startswith('p') and orig_prop in hmy_lookup:
                urls.append(transform_p_code_url(encoded_url, hmy_lookup[orig_prop]))
                print(transform_p_code_url(encoded_url, hmy_lookup[orig_prop]))

            success_res = None
            for u in urls:
                for dom in [None] + FALLBACK_DOMAINS:
                    try:
                        curr_url = u.replace(PRIMARY_DOMAIN, dom) if dom else u
                        
                        r = session.get(curr_url, timeout=15)
                        if r.status_code == 200: success_res = r; break
                    except: pass
                if success_res: break
            
            if not success_res: raise Exception("File could not be downloaded (404/Timeout).")

            i_type_str = str(row.get('iType', '0')).strip()
            
            # CHECK IF TARGET IMAGE NAME IS PROVIDED TO DETERMINE FORMAT
            target_image_name = str(row.get('Target Image Name', '')).strip()
            target_image_name_clean = target_image_name if (target_image_name and target_image_name.lower() != 'nan') else ''
            
            # Determine save format based on target image name extension (if provided) or auto-detect
            if target_image_name_clean:
                _, ext = os.path.splitext(target_image_name_clean)
                ext_lower = ext.lower()
                if ext_lower in ['.png']:
                    save_format = "PNG"
                elif ext_lower in ['.jpg', '.jpeg']:
                    save_format = "JPEG"
                else:
                    # Default based on iType if extension not recognized
                    save_format = "PNG" if i_type_str == '6' or (i_type_str in ['2', '40'] and 'png' in success_res.url.lower()) else "JPEG"
            else:
                # Auto-detect format
                save_format = "PNG" if i_type_str == '6' or (i_type_str in ['2', '40'] and 'png' in success_res.url.lower()) else "JPEG"
            
            save_ext = ".png" if save_format == "PNG" else ".jpg"
            img = Image.open(BytesIO(success_res.content)).convert('RGBA' if save_format == "PNG" else 'RGB')

            action = "Kept Original"
            if is_resize_mode:
                orig_w, orig_h = img.size
                if manual_sizing:
                    box_w, box_h = (cfg["targetwidth"], cfg["targetheight"])
                else:
                    box_w, box_h = get_target_box(i_type_str, prop_type)
                
                if box_w and box_h:
                    final_w, final_h = (box_w, box_h) if manual_sizing else get_scaled_dimensions(orig_w, orig_h, box_w, box_h, downscale_only=True)
                    if manual_sizing or (orig_w != final_w) or (orig_h != final_h):

                        if (not manual_sizing) and orig_h > orig_w:
                            img = process_vertical_image(img)
                            curr_w, curr_h = img.size
                            final_w, final_h = get_scaled_dimensions(curr_w, curr_h, box_w, box_h, downscale_only=True)
                            img = img.resize((final_w, final_h), Image.Resampling.LANCZOS)
                            action = f"Vertical Crop & Resized {final_w}x{final_h}"
                        else:
                            img = img.resize((final_w, final_h), Image.Resampling.LANCZOS)
                            action = f"Resized to {final_w}x{final_h}"
                    else:
                        action = "Kept (Smaller than Target)"

            # CHECK IF TARGET IMAGE NAME IS PROVIDED
            if target_image_name_clean:
                # Use the provided target image name directly (but clean illegal path characters)
                # Remove illegal filename characters: / \ : * ? " < > |
                cleaned_target_name = re.sub(r'[/\\:*?"<>|]', '_', target_image_name_clean)
                cleaned_target_name = re.sub(r'_+', '_', cleaned_target_name).strip('_')
                
                # Check if target image name already has an extension
                _, ext = os.path.splitext(cleaned_target_name)
                if ext:
                    # Extension provided by user - use as-is
                    final_filename = cleaned_target_name
                else:
                    # No extension provided - add the detected extension
                    final_filename = cleaned_target_name + save_ext
            else:
                # SMART NAMING LOGIC (original logic)
                url_fn = get_filename_from_url(success_res.url)
                fn_no_ext = os.path.splitext(url_fn)[0]
                sanitized_fn = clean_string(fn_no_ext)
                
                while sanitized_fn.lower().startswith(clean_orig.lower()):
                    sanitized_fn = sanitized_fn[len(clean_orig):].lstrip('_')
                
                doc_abbr = get_doc_type_abbreviation(doc_type_val)
                name_parts = [clean_target, sanitized_fn]
                
                # Add iType Suffix if not already present
                if i_type_str and i_type_str != '0' and (i_type_str.lower() not in sanitized_fn.lower().split('_')): 
                    name_parts.append(i_type_str)
                
                # ADD DOC TYPE SUFFIX (Optimized Logic)
                if doc_abbr and doc_abbr != 'XX':
                    keywords = SHORTHAND_CHECK.get(doc_abbr, [doc_abbr.lower()])
                    # Remove spaces and underscores for a robust check against concatenated keywords
                    normalized_name = fn_no_ext.lower().replace('_', '').replace(' ', '')
                    
                    is_already_described = False
                    for kw in keywords:
                        if kw.lower() in normalized_name:
                            is_already_described = True
                            break
                    
                    if not is_already_described:
                        name_parts.append(doc_abbr)
                
                if add_opt_suffix:
                    name_parts.append("Optimized")

                final_filename = "_".join([p for p in name_parts if p]) + save_ext
            save_path = os.path.join(target_subfolder, final_filename)
            
            final_mb = compress_and_save(img, save_path, max_mb, format_type=save_format)
            print(f"[{base_log.format(status=' OK ')}] {action} | {final_mb:.2f} MB")
            process_log.append({
                'Folder': target_subfolder,
                'status': 'success',
                'Original': raw_url,
                'New': save_path,
                'SizeMB': round(final_mb, 2),
                'Error': ''
            })

        except Exception as e:
            print(f"[{base_log.format(status='FAIL')}] {e}")
            row_dict = row.to_dict(); row_dict['Error_Reason'] = str(e); failed_records.append(row_dict)
            process_log.append({
                'Folder': target_subfolder if 'target_subfolder' in locals() else output_folder,
                'status': 'fail',
                'Original': str(row.get('Full Path', '')),
                'New': '',
                'SizeMB': 0,
                'Error': str(e)
            })

    if process_log:
        log_df = pd.DataFrame(process_log)
        log_file = os.path.join(output_folder, "Process_Log.csv")
        log_df.to_csv(log_file, index=False)
        print(f"[INFO] Saved process log: {log_file}")

    if failed_records:
        error_df = pd.DataFrame(failed_records)
        try:
            error_df.to_excel(os.path.join(output_folder, "Failed_Log.xlsx"), index=False)
        except:
            error_df.to_csv(os.path.join(output_folder, "Failed_Log.csv"), index=False)
            print("[INFO] Saved Failed_Log as CSV.")

if __name__ == "__main__":
    try: main_logic()
    except Exception as e: print(f"FATAL ERROR: {e}")
    finally: input("\nProcess Complete. Press ENTER to close...")