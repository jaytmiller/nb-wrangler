| Symbol / Node | Meaning |
|---------------|---------|
| **🗂️ Wrangler spec** | The user‑provided YAML that lists which repositories to fetch. |
| **🔧 nb‑wrangler --curate-data** | Entry‑point command that orchestrates the whole flow. |
| **📂 Clone all selected repos** | All repos listed in the spec are cloned locally. |
| **refdata_dependencies.yaml** | Optional file inside a repo describing data groups, archive URLs, unpack locations, nested roots, and the environment variable that points to the final data location. |
| **📑 Named groups → 🔗 N web refs → 📂 Target paths → 📂 “nested root” → 🌐 Env‑var** | The hierarchy of information encoded in the `refdata_dependencies.yaml`. |
| **🗳️ Select repo from `system.primary_repo`** | When more than one cloned repo supplies a `refdata_dependencies.yaml`, the “winner” is chosen via the `system.primary_repo` field. |
| **⬇️ Download each archive** | All archive URLs from the selected yaml are fetched. |
| **📦 Unpack under `<pantry>/…`** | Archives are extracted into the nb‑wrangler “pantry” directory, respecting the *unpack path* + *nested root*. |
| **🔐 Compute sha256** | A SHA‑256 hash is calculated for each archive and stored back into the spec for future integrity checks. |
| **📄 Refdata‑format / Pantry‑relative format** | Two env‑var files are emitted: one that matches the exact install locations defined by the yaml, and another that uses paths relative to the shared pantry directory. |
| **⚙️ Inject into kernel‑metadata .json** | The generated environment variables are automatically added to the Jupyter kernel’s `kernel.json`, making them available inside notebooks. |
| **💻 Optional `nb‑wrangler export`** | A command that prints `export VAR=...` lines for use in a terminal shell. |
