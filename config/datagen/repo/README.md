# lamina

Layered configuration files for Python, with includes and environment interpolation. No runtime dependencies.

```python
import lamina

doc = lamina.load("app.conf", env=os.environ)
doc.get("db.host")
lamina.dumps(doc)   # writes it back exactly as it was, with your edits
```

- `[section]` headers, `key = value` entries, `#` and `;` comments, blank lines: all preserved on write.
- `@include "base.conf"`: values from included files, overridden by the including file. Paths stay inside the
  project root.
- `${NAME}` and `${NAME:-default}`: expanded from the environment you pass in.
