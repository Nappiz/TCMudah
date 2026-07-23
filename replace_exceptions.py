import os
import re

directories = [
    os.path.join("app", "routers"),
    os.path.join("app", "core")
]

error_map = {
    "400": "BadRequestError",
    "401": "UnauthorizedError",
    "403": "ForbiddenError",
    "404": "NotFoundError",
}

for d in directories:
    for filename in os.listdir(d):
        if not filename.endswith(".py"):
            continue
        filepath = os.path.join(d, filename)
        
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        # Find all exceptions used to know what to import
        used_exceptions = set()
        
        def replacer(match):
            status = match.group(1)
            detail = match.group(2)
            exc_name = error_map.get(status, "AppException")
            if exc_name != "AppException":
                used_exceptions.add(exc_name)
                return f"raise {exc_name}(detail={detail})"
            else:
                used_exceptions.add("AppException")
                return f"raise AppException(status_code={status}, detail={detail})"
        
        # Replace raise HTTPException(status_code=X, detail=Y)
        new_content, count = re.subn(r'raise\s+HTTPException\s*\(\s*status_code\s*=\s*(\d+)\s*,\s*detail\s*=\s*(.*?)\s*\)', replacer, content)
        
        if count > 0:
            # Remove HTTPException from fastapi imports
            new_content = re.sub(r',\s*HTTPException', '', new_content)
            new_content = re.sub(r'HTTPException\s*,?\s*', '', new_content)
            # if 'from fastapi import ' becomes empty or weird, we might need a better regex, but let's assume it's fine
            new_content = re.sub(r'from fastapi import\s*\n', 'from fastapi import\n', new_content)

            # Add imports
            imports_str = ", ".join(sorted(list(used_exceptions)))
            import_statement = f"from app.errors.exceptions import {imports_str}\n"
            
            # Put it after the first couple of imports
            parts = new_content.split('\n')
            for i, line in enumerate(parts):
                if line.startswith("from app.") or line.startswith("import "):
                    parts.insert(i, import_statement)
                    break
            else:
                parts.insert(0, import_statement)
                
            new_content = "\n".join(parts)
            
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(new_content)
            print(f"Updated {filepath}")
