import os
import json
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from utils.logger import api_logger as logger


# Google Sheets API connector
# https://console.cloud.google.com/apis/library?hl=ru&inv=1&invt=Abtb0w&project=myhome-455318

class GoogleConnector:
  def __init__(self, strict=True, allow_console_auth=False):
    from utils.configs import get_data_dir
    
    # Используем универсальную функцию для определения пути к data
    self.store_path = get_data_dir()
    self.creds_path = os.path.join(self.store_path, "google_token.json")  # access/refresh токены
    self.auth_path = os.path.join(self.store_path + '_src', "google_credentials.json")  # credentials для авторизации
    self.creds = None
    self.service = None
    self.strict = strict
    self.allow_console_auth = allow_console_auth  # Разрешить автоматическое открытие браузера через консоль
    self.enabled = self._authorize()

  def _authorize(self):
    SCOPES = ["https://www.googleapis.com/auth/spreadsheets", 'https://www.googleapis.com/auth/drive']
    os.makedirs(self.store_path, exist_ok=True)

    if os.path.exists(self.creds_path):
      self.creds = Credentials.from_authorized_user_file(self.creds_path, SCOPES)
    elif os.path.exists(self.auth_path):
      # Если allow_console_auth=False, не открываем браузер автоматически
      # Токен должен быть получен через UI
      if not self.allow_console_auth:
        logger.info("[GoogleConnector] Токен не найден. Получите токен через UI в настройках аддона.")
        return False
      
      flow = InstalledAppFlow.from_client_secrets_file(self.auth_path, SCOPES)
      # Проверяем, есть ли графический интерфейс (не в Docker)
      try:
        import webbrowser
        webbrowser.get()
        self.creds = flow.run_local_server(port=0)
        with open(self.creds_path, 'w') as token:
          token.write(self.creds.to_json())
      except Exception as e:
        logger.warning(f"GoogleConnector failed to open browser for authorization: {e}")
        logger.warning("GoogleConnector working in headless mode - authorization disabled")
        return False
    else:
      msg = "[GoogleConnector] Не найдены ни google_service_account.json, ни google_credentials.json"
      if self.strict:
        raise FileNotFoundError(msg)
      else:
        logger.warning(msg)
        return False

    if self.creds and self.creds.expired and self.creds.refresh_token:
      self.creds.refresh(Request())

    try:
      self.service = build('sheets', 'v4', credentials=self.creds)
      logger.success("GoogleConnector authorization successful")
      return True
    except Exception as e:
      if self.strict:
        raise RuntimeError(f"[GoogleConnector] Ошибка авторизации: {e}")
      else:
        logger.error(f"GoogleConnector authorization failed: {e}")
        return False

  def gsheet_add_row(
      self,
      sheet: str,
      page: str,
      data: list[list[str]],
      create_sheet_if_missing: bool = True,
      create_tab_if_missing: bool = True,
      with_header: list[str] = None,
      value_input_option: str = "USER_ENTERED",
      insert_data_option: str = "INSERT_ROWS",
      deduplicate: bool = True,
      dedup_last_n: int = 100,
      max_rows: int = 0,
      batch_size: int = 500,
  ):
    if not self.enabled:
      logger.warning("GoogleConnector Sheets API disabled, data not written")
      return

    if not sheet or not page or not data:
      logger.error("GoogleConnector parameters sheet, page and data are required")
      return

    try:
      # 1. Получаем spreadsheetId по имени или ID
      spreadsheet = None
      spreadsheet_id = sheet
      if len(sheet) < 40:  # похоже на название
        from googleapiclient.discovery import build as build_drive
        drive_service = build_drive('drive', 'v3', credentials=self.creds)
        result = drive_service.files().list(
          q=f"name = '{sheet}' and mimeType='application/vnd.google-apps.spreadsheet'",
          spaces='drive',
          fields='files(id, name)',
          pageSize=1
        ).execute()
        files = result.get('files', [])
        if not files and create_sheet_if_missing:
          spreadsheet = self.service.spreadsheets().create(
            body={"properties": {"title": sheet}}
          ).execute()
          spreadsheet_id = spreadsheet["spreadsheetId"]
          logger.info(f"GoogleConnector created new spreadsheet: {sheet}")
        elif files:
          spreadsheet_id = files[0]["id"]
        else:
          logger.error(f"GoogleConnector spreadsheet '{sheet}' not found")
          return

      # 2. Проверяем вкладку
      spreadsheet = self.service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
      sheets = spreadsheet.get("sheets", [])
      tab_titles = [s["properties"]["title"] for s in sheets]

      if page not in tab_titles and create_tab_if_missing:
        self.service.spreadsheets().batchUpdate(
          spreadsheetId=spreadsheet_id,
          body={"requests": [{"addSheet": {"properties": {"title": page}}}]}
        ).execute()
        logger.info(f"GoogleConnector added tab: {page}")

        if with_header:
          self.service.spreadsheets().values().append(
            spreadsheetId=spreadsheet_id,
            range=f"{page}!A1",
            valueInputOption="RAW",
            insertDataOption="INSERT_ROWS",
            body={"values": [with_header]}
          ).execute()

      # 3. Получаем последние N строк для dedup
      existing_rows = set()
      if deduplicate:
        fetch_range = f"{page}!A1:Z{dedup_last_n + 1}"
        resp = self.service.spreadsheets().values().get(
          spreadsheetId=spreadsheet_id,
          range=fetch_range
        ).execute()
        existing_rows = set(tuple(row) for row in resp.get("values", []))

      # 4. Вставка батчами с поэтапным dedup
      inserted = 0
      for i in range(0, len(data), batch_size):
        chunk = data[i:i + batch_size]
        if deduplicate:
          chunk = [row for row in chunk if tuple(row) not in existing_rows]

        if not chunk:
          continue

        self.service.spreadsheets().values().append(
          spreadsheetId=spreadsheet_id,
          range=f"{page}!A1",
          valueInputOption=value_input_option,
          insertDataOption=insert_data_option,
          body={"values": chunk}
        ).execute()

        for row in chunk:
          existing_rows.add(tuple(row))

        inserted += len(chunk)
        logger.debug(f"GoogleConnector[{page}] inserted batch: {len(chunk)} rows")

      if inserted == 0:
        logger.info(f"GoogleConnector[{page}] No new rows to insert")

      # 5. Лимит строк: если max_rows задан
      if max_rows > 0:
        result = self.service.spreadsheets().values().get(
          spreadsheetId=spreadsheet_id,
          range=f"{page}!A1:Z",
          majorDimension="ROWS"
        ).execute()
        all_rows = result.get("values", [])
        if len(all_rows) > max_rows:
          num_to_delete = len(all_rows) - max_rows
          sheet_id = next(
            s["properties"]["sheetId"] for s in sheets if s["properties"]["title"] == page
          )
          logger.info(f"GoogleConnector deleting {num_to_delete} old rows from {page}")
          self.service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={
              "requests": [{
                "deleteDimension": {
                  "range": {
                    "sheetId": sheet_id,
                    "dimension": "ROWS",
                    "startIndex": 1,
                    "endIndex": 1 + num_to_delete
                  }
                }
              }]
            }
          ).execute()
      return True

    except Exception as err:
      logger.error(f"GoogleConnector error writing to spreadsheet: {err}")
      logger.error(f"GoogleConnector data not written: {data}")
      logger.error(
        f"GoogleConnector parameters: sheet={sheet}, page={page}, create_sheet_if_missing={create_sheet_if_missing}")
      return False
