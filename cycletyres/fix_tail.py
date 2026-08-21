with open('views.py', 'r', encoding='utf-8') as f:
    lines = f.read().splitlines()

while lines and not lines[-1].strip():
    lines.pop()

if '@permission_classes' in lines[-1]:
    lines.pop()
if '@api_view' in lines[-1]:
    lines.pop()

with open('views.py', 'w', encoding='utf-8') as f:
    f.write('\n'.join(lines) + '\n')
