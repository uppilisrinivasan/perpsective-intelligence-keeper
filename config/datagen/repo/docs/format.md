# The lamina format

A file is a sequence of lines: section headers (`[name]`), entries (`key = value`), comments (`#` or `;`),
blank lines and include directives (`@include "path"`). Values are strings; interpretation is up to you.
