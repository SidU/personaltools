#!/usr/bin/env node
import { promises as fs } from 'fs';

const headers = {
  'Accept': 'application/json, text/plain, */*',
  'Accept-Language': 'en-US,en;q=0.9',
  'Cache-Control': 'no-cache',
  'Origin': 'https://teams.microsoft.com',
  'Referer': 'https://teams.microsoft.com/',
  'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
};

async function main() {
  const configUrl = 'https://config.edge.skype.com/config/v1/MicrosoftTeams/1.0.0.0?agents=MicrosoftTeamsAppCatalog';
  const configRes = await fetch(configUrl, { headers });
  if (!configRes.ok) {
    throw new Error(`Failed to fetch config: ${configRes.status}`);
  }
  const config = await configRes.json();
  const sources = config?.MicrosoftTeamsAppCatalog?.appCatalog?.storeAppDefinitions?.sources;
  if (!Array.isArray(sources)) {
    throw new Error('No store app definition sources found');
  }

  await fs.mkdir('bot_apps', { recursive: true });

  for (const url of sources) {
    console.log(`Fetching ${url}`);
    const res = await fetch(url, { headers });
    if (!res.ok) {
      console.warn(`Failed to download ${url}: ${res.status}`);
      continue;
    }
    const data = await res.json();
    if (data?.value?.appDefinitions) {
      for (const app of data.value.appDefinitions) {
        if (Array.isArray(app.bots) && app.bots.length > 0) {
          const filePath = `bot_apps/${app.id}.json`;
          await fs.writeFile(filePath, JSON.stringify(app, null, 2));
          console.log(`Saved ${filePath}`);
        }
      }
    }
  }
}

main().catch(err => {
  console.error(err);
  process.exit(1);
});
