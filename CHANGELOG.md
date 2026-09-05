# Changelog

## 0.3.0 (2026-09-05)

* The UCI conversation and every chess question behind it now go through the in-house
  [esca](https://github.com/AnglerfishChess/esca) library. The MCP tools are unchanged: same names, same
  arguments, same answers.
* Python 3.12 or newer is required.
* `-o NAME VALUE` on the command line now actually reaches the engine.
* `mcp` 1.28.1 or newer; the lockfile is refreshed past every advisory GitHub had open against it.
