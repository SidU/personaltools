import os
import json
import argparse
import openai

INPUT_DIR = 'bot_apps'
OUTPUT_DIR = 'augmented_defs'
os.makedirs(OUTPUT_DIR, exist_ok=True)

def get_description(app):
    for key in ['shortDescription', 'longDescription', 'description']:
        desc = app.get(key)
        if isinstance(desc, str) and desc.strip():
            return desc
    return ''

def get_commands(app):
    cmds = []
    bots = app.get('bots') or []
    for bot in bots:
        for cl in bot.get('commandLists', []):
            for cmd in cl.get('commands', []):
                title = cmd.get('title')
                if title and title not in cmds:
                    cmds.append(title)
    return cmds

openai.api_key = os.getenv('OPENAI_API_KEY')

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--force', action='store_true',
                        help='re-augment all bots')
    args = parser.parse_args()

    processed = {
        f for f in os.listdir(OUTPUT_DIR)
        if f.endswith('.json')
    }

    for fname in sorted(os.listdir(INPUT_DIR)):
        if not fname.endswith('.json'):
            continue

        if not args.force and fname in processed:
            print('Skipping', fname)
            continue

        in_path = os.path.join(INPUT_DIR, fname)
        out_path = os.path.join(OUTPUT_DIR, fname)

        with open(in_path, 'r', encoding='utf-8') as f:
            app = json.load(f)

        bot_name = app.get('name', 'bot')
        print('Augmenting', bot_name)
        description = get_description(app)[:400]
        commands = get_commands(app)

        prompt = (
            "Bot name: {name}\n"
            "Description: {desc}\n"
            "Commands: {cmds}\n\n"
            "Generate 3 example user prompts for Microsoft Teams where a user would @mention the bot to accomplish tasks."
            " Only reference commands from the provided list, if any."
            " Respond ONLY with raw JSON (no code fences) as an array of objects with keys 'prompt', 'description', and optional 'command'."
        ).format(name=bot_name, desc=description, cmds=', '.join(commands))

        try:
            response = openai.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "You generate example user prompts for a Teams bot."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=200,
            )
            txt = response.choices[0].message.content.strip()
            if txt.startswith('```'):
                txt = txt.strip('`')
                if txt.startswith('json'):
                    txt = txt[4:].strip()
            examples = json.loads(txt)
        except Exception as e:
            print('Failed on', fname, e)
            examples = []

        app['examplePrompts'] = examples

        with open(out_path, 'w', encoding='utf-8') as f:
            json.dump(app, f, ensure_ascii=False, indent=2)

    print('Done')


if __name__ == '__main__':
    main()
