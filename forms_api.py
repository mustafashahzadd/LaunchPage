import os
import pickle
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# Scopes needed for Google Forms API
SCOPES = [
    "https://www.googleapis.com/auth/forms.body",
    "https://www.googleapis.com/auth/forms.responses.readonly"
]

# Token storage
TOKEN_FILE = "token.pkl"
CREDENTIALS_FILE = "credentials.json" # Downloaded from Google Clouad Console

def get_credentials():
    """Load or request OAuth credentials."""
    creds = None
    
    # Load token if available
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, "rb") as token:
            creds = pickle.load(token)
    
    # If no valid creds, log in
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                CREDENTIALS_FILE, SCOPES
            )
            creds = flow.run_local_server(port=0)
        
        # Save token for next time
        with open(TOKEN_FILE, "wb") as token:
            pickle.dump(creds, token)
    
    return creds

def create_google_form(title="Workshop Registration Form", description="Auto-generated registration form"):
    """Creates a Google Form and returns its URLs."""
    creds = get_credentials()
    service = build("forms", "v1", credentials=creds)
    
    # ✅ Step 1: Create the form with ONLY title
    form = service.forms().create(body={"info": {"title": title}}).execute()
    
    # ✅ Step 2: Use batchUpdate to set description and questions
    requests = [
        {
            "updateFormInfo": {
                "info": {"title": title, "description": description},
                "updateMask": "description"
            }
        },
        {
            "createItem": {
                "item": {
                    "title": "Full Name",
                    "questionItem": {
                        "question": {"required": True, "textQuestion": {}}
                    }
                },
                "location": {"index": 0}
            }
        },
        {
            "createItem": {
                "item": {
                    "title": "Email Address",
                    "questionItem": {
                        "question": {"required": True, "textQuestion": {}}
                    }
                },
                "location": {"index": 1}
            }
        },
        {
            "createItem": {
                "item": {
                    "title": "Organization / Company",
                    "questionItem": {"question": {"textQuestion": {}}}
                },
                "location": {"index": 2}
            }
        }
    ]
    
    service.forms().batchUpdate(
        formId=form["formId"],
        body={"requests": requests}
    ).execute()
    
    return {
        "formId": form["formId"],
        "editUrl": f"https://docs.google.com/forms/d/{form['formId']}/edit",
    }

if __name__ == "__main__":
    urls = create_google_form()
    print("✅ Google Form created successfully!")
    print("Edit URL:", urls["editUrl"])
    