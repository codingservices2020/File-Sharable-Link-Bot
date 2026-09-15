import sys
import os
from pcloud_client import PyCloud

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

from dotenv import load_dotenv
load_dotenv()

PCLOUD_EMAIL = os.getenv("PCLOUD_EMAIL")
PCLOUD_PASSWORD = os.getenv("PCLOUD_PASSWORD")

# Log in to pCloud
pc = PyCloud(PCLOUD_EMAIL, PCLOUD_PASSWORD)


# 1. List all files/folders in root
def list_root():
    print("📂 Files in your root folder:")
    result = pc.listfolder(folderid=0)
    files = result.get('metadata', {}).get('contents', [])
    for item in files:
        if not item.get('isfolder'):
            print(f" - {item['name']} (fileid: {item['fileid']})")
        else:
            print(f" 📁 {item['name']} (folder)")
    return files


# 2. Create folder (or return existing)
def create_folder(folder_name):
    """
    Creates a folder in pCloud (or returns the existing folder ID).
    Supports relative names like 'WebUploads' or paths like '/Uploaded Reports/WebUploads'.
    """
    folder_path = folder_name if folder_name.startswith('/') else f"/{folder_name}"
    response = pc.createfolder(path=folder_path)

    if response.get('result') == 0:
        folder_id = response['metadata']['folderid']
        print(f"📁 Folder created: {folder_path} (ID: {folder_id})")
        return folder_id

    elif response.get('result') == 2004:  # Folder already exists
        list_resp = pc.listfolder(path=folder_path)
        if list_resp.get("result") == 0 and "metadata" in list_resp:
            folder_id = list_resp['metadata']['folderid']
            print(f"📁 Folder already exists: {folder_path} (ID: {folder_id})")
            return folder_id
        else:
            raise Exception(f"❌ Failed to access existing folder '{folder_path}': {list_resp}")

    elif response.get('result') == 2005:  # Directory not found (parent folder missing)
        parts = [p for p in folder_path.strip('/').split('/') if p]
        curr_id = 0
        current_acc_path = ""
        for part in parts:
            current_acc_path += f"/{part}"
            res = pc.createfolder(path=current_acc_path)
            if res.get('result') == 0:
                curr_id = res['metadata']['folderid']
            elif res.get('result') == 2004:
                list_res = pc.listfolder(path=current_acc_path)
                curr_id = list_res['metadata']['folderid']
            else:
                raise Exception(f"❌ Failed to create folder segment '{current_acc_path}': {res}")
        return curr_id

    else:
        raise Exception(f"❌ Failed to create/access folder: {response}")


# 3. Upload file to a folder
def upload_file(folder_id, local_file_path):
    if not os.path.exists(local_file_path):
        raise FileNotFoundError(f"Local file not found: {local_file_path}")

    result = pc.uploadfile(files=[local_file_path], folderid=folder_id)
    if result.get('result') == 0 and 'metadata' in result and len(result['metadata']) > 0:
        file_info = result['metadata'][0]
        print(f"✅ Uploaded: {file_info['name']} (fileid: {file_info['fileid']})")
        return file_info['fileid']
    else:
        raise Exception(f"❌ Failed to upload file: {result}")


# 4. Generate public + short link
def generate_share_link(file_id):
    data = pc.getfilepublink(fileid=file_id, shortlink=1)
    if data.get("result") == 0:
        link = data.get("link")
        linkid = data.get("linkid")
        shortlink = data.get("shortlink")
        if not shortlink:
            resp = pc.changepublink(linkid=linkid, shortlink=1)
            shortlink = resp.get("shortlink")
        link_data = {
            "link": link,
            "shortlink": shortlink or link,
            "linkid": linkid
        }
        return link_data
    else:
        raise Exception(f"❌ Failed to create public link: {data}")


# 5. Force shortlink creation for an existing link
def force_shortlink(linkid):
    resp = pc.changepublink(linkid=linkid, shortlink=1)
    return resp.get("shortlink")


# 6. Delete a file by ID
def delete_file(file_id):
    resp = pc.deletefile(fileid=file_id)
    if resp.get("result") == 0:
        print(f"🗑️ File deleted: fileid={file_id}")
    else:
        print(f"❌ Failed to delete: {resp}")
    return resp


if __name__ == "__main__":
    folder_id = create_folder("WebUploads")
    print(f"Target Folder ID: {folder_id}")