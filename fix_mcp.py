import re
import os

file_path = 'engine/mcp_server.py'

if not os.path.exists(file_path):
    print("❌ Error: No se encontró engine/mcp_server.py")
    exit(1)

with open(file_path, 'r', encoding='utf-8') as f:
    code = f.read()

# --- 1. Arreglar world_check ---
if '@mcp.tool()\ndef world_check' not in code and '@mcp.tool()\nasync def world_check' not in code:
    # Busca 'def world_check' o 'async def world_check' y le añade el decorador arriba
    code = re.sub(r'(?<!@mcp\.tool\(\)\n)(async )?def world_check', r'@mcp.tool()\n\1def world_check', code)
    print("✅ Decorador @mcp.tool() añadido a la función world_check.")
else:
    print("ℹ️ world_check ya tenía el decorador.")

# --- 2. Arreglar list_styles ---
# Busca la función list_styles y la reemplaza por una versión que cuenta dinámicamente
pattern = r'def list_styles\([^)]*\):.*?(?=\ndef |\n@|\Z)'
match = re.search(pattern, code, re.DOTALL)

if match:
    old_func = match.group(0)
    new_func = '''def list_styles() -> list[str]:
    """
    Returns the available styles, dynamically counted from the styles folder.
    """
    styles_dir = os.path.join(os.path.dirname(__file__), "styles")
    if not os.path.exists(styles_dir):
        styles_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "styles")
    
    if not os.path.exists(styles_dir):
        return []
        
    return [d for d in os.listdir(styles_dir) if os.path.isdir(os.path.join(styles_dir, d))]
'''
    code = code.replace(old_func, new_func)
    print("✅ Función list_styles actualizada para contar dinámicamente los estilos.")
else:
    print("⚠️ No se encontró la función list_styles, puede que tenga otro nombre.")

# Guardar los cambios
with open(file_path, 'w', encoding='utf-8') as f:
    f.write(code)
    
print("✅ Archivo guardado correctamente.")
