import os
from google.oauth2 import service_account
from googleapiclient.discovery import build

# Configuration
CREDENTIALS_FILE = r'D:\Contenfactory\API\nha-may-content-208dc5165e29.json'
SPREADSHEET_TITLE = 'Content Factory - Video Manager'

# Scopes
SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]

def setup_spreadsheet():
    # Authenticate
    creds = service_account.Credentials.from_service_account_file(
        CREDENTIALS_FILE, scopes=SCOPES)
    
    sheets_service = build('sheets', 'v4', credentials=creds)
    drive_service = build('drive', 'v3', credentials=creds)

    # 1. Create Spreadsheet
    spreadsheet_body = {
        'properties': {
            'title': SPREADSHEET_TITLE
        }
    }
    
    spreadsheet = sheets_service.spreadsheets().create(
        body=spreadsheet_body, fields='spreadsheetId').execute()
    
    spreadsheet_id = spreadsheet.get('spreadsheetId')
    print(f"Spreadsheet created with ID: {spreadsheet_id}")

    # 2. Add 'Channels' headers and 'Videos' sheet
    # Rename first sheet to 'Channels' and add headers
    # Create second sheet 'Videos' and add headers
    
    requests = [
        # Rename Sheet1 to Channels
        {
            'updateSheetProperties': {
                'properties': {
                    'sheetId': 0,
                    'title': 'Channels'
                },
                'fields': 'title'
            }
        },
        # Add Videos sheet
        {
            'addSheet': {
                'properties': {
                    'title': 'Videos'
                }
            }
        }
    ]
    
    sheets_service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={'requests': requests}
    ).execute()

    # Get the sheet IDs
    spreadsheet_info = sheets_service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    sheets = spreadsheet_info.get('sheets', [])
    
    channels_id = sheets[0]['properties']['sheetId']
    videos_id = sheets[1]['properties']['sheetId']

    # Add Headers
    header_data = [
        {
            'range': 'Channels!A1:F1',
            'values': [['Platform', 'Channel Link', 'Channel Name', 'Topic', 'Last Video URL', 'Status']]
        },
        {
            'range': 'Videos!A1:F1',
            'values': [['Video Link', 'Platform', 'Topic', 'Download Status', 'File Path', 'Created At']]
        }
    ]
    
    sheets_service.spreadsheets().values().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={
            'valueInputOption': 'RAW',
            'data': header_data
        }
    ).execute()

    # 3. Share the spreadsheet (Anyone with the link can edit)
    # Note: This works if the Google Cloud project allows it.
    permission_body = {
        'type': 'anyone',
        'role': 'writer'
    }
    
    try:
        drive_service.permissions().create(
            fileId=spreadsheet_id,
            body=permission_body
        ).execute()
        print("Permission set to 'Anyone with the link can edit'.")
    except Exception as e:
        print(f"Could not set public permissions: {e}")
        print(f"Please share the sheet manually with: {creds.service_account_email}")

    url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/edit"
    print(f"\nYour Google Sheet is ready: {url}")
    return url

if __name__ == '__main__':
    setup_spreadsheet()
