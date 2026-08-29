import os, re

folder = 'templates'
for filename in os.listdir(folder):
    if filename.endswith('.html'):
        path = os.path.join(folder, filename)
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        new_content = re.sub(r"\{\{ _\('(.+?)'\) \}\}", r'\1', content)
        if new_content != content:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(new_content)
            print(f'Fixed: {filename}')
print('Done!')