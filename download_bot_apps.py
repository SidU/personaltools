import json
import os
from urllib import request, error

HEADERS = {
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'en-US,en;q=0.9',
    'Cache-Control': 'no-cache',
    'Origin': 'https://teams.microsoft.com',
    'Referer': 'https://teams.microsoft.com/',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

CONFIG_URL = 'https://config.edge.skype.com/config/v1/MicrosoftTeams/1.0.0.0?agents=MicrosoftTeamsAppCatalog'


def fetch_json(url):
    req = request.Request(url, headers=HEADERS)
    with request.urlopen(req) as resp:
        data = resp.read().decode('utf-8')
        return json.loads(data)


def main():
    try:
        config = fetch_json(CONFIG_URL)
    except Exception as e:
        raise SystemExit(f"Failed to fetch catalog configuration: {e}")

    sources = config.get('MicrosoftTeamsAppCatalog', {}).get('appCatalog', {}).get('storeAppDefinitions', {}).get('sources')
    if not isinstance(sources, list):
        raise SystemExit('No store app definition sources found')

    os.makedirs('bot_apps', exist_ok=True)

    for src in sources:
        try:
            print(f'Fetching {src}')
            data = fetch_json(src)
        except Exception as e:
            print(f'Failed to download {src}: {e}')
            continue

        app_defs = data.get('value', {}).get('appDefinitions')
        if not isinstance(app_defs, list):
            continue

        for app in app_defs:
            bots = app.get('bots')
            if isinstance(bots, list) and len(bots) > 0:
                app_id = app.get('id')
                if app_id:
                    file_path = os.path.join('bot_apps', f'{app_id}.json')
                    with open(file_path, 'w', encoding='utf-8') as f:
                        json.dump(app, f, ensure_ascii=False, indent=2)
                    print(f'Saved {file_path}')


if __name__ == '__main__':
    main()
