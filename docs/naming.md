# Names and how they are related

nb-wrangler defines and creates a number of different named entities that
typically are interrelated by similarity or defaulting behavior:

- image_name
- kernel_name
- environment_name
- display_name
- shelf_name

The `image_name` defines the most prominent naming substring for Docker images derived from a wrangler spec, built on GitHub, and used on the science-platforms. Typically this will correspond to different calendar versions of mission oriented application software built into an image. The image_name has a first class field defining it in the wrangler spec. Ultimately a substring of the pipeline-built image's name will appear in the Spawner menu on JupyterHub

The `kernel_name` defines the name of a JupyterLab kernel corresponding to a Wrangler spec, i.e. the name of the lab kernel associated with the mission oriented mamba environment defined in a spec.  The kernel_name drives where the kernel spec is stored and how it is named.  It is resolved through the following priority chain:

1. The `kernel_name` field in the `image_spec_header` section of the wrangler spec (the first class field).
2. The `name` field of an inline mamba spec (when no header `kernel_name` is present).
3. The compiled output `kernel_name` stored in the spec output section (for external specs that must be fetched and parsed by the compiler first).

The `environment_name` names the mamba environment in which the Wrangler spec's mamba and pip packages are installed.  It may be specified explicitly in the `image_spec_header` as `environment_name`, which trumps all other defaulting mechanisms.  When unspecified, it is a derived property of `kernel_name`, following the convention that the 'python3' kernel and the 'base' conda environment refer to the same thing (python3 is mapped to base).  When kernel_name is unspecified, environment_name defaults to image_name.

One of the most notable exceptions to the rule that kernel_name == environment_name is the naming of the base environment and kernel on our platform JupyterHub installations: there the environment is named "base" but the kernel is named "python3" which distinguishes it from other completely different kernels like "Julia" or "R".  Other reasons kernel_name's may differ from environment_name's are to set different startup switches or environment variables in the kernel.

The `display_name` defines how a particular kernel will be displayed in the JupyterLab menu used to select a kernel for a notebook.  The display_name has a first class field in the wrangler spec header but will default to the kernel_name if not specified.  If both display_name and kernel_name are unspecified, it returns `None`.

The `shelf_name` is the directory name where the persistent code and data files and archives are stored for one spec / kernel / environment.  It may be specified explicitly in the `image_spec_header` as `shelf_name`, which trumps all other defaulting.  When unspecified, it defaults to the fully resolved `environment_name` (with the `python3` → `base` mapping applied).  When `environment_name` cannot be determined (no `kernel_name`, no explicit header), it falls back to `moniker` (the filesystem-safe `image_name` with spaces replaced by dashes).  This ensures that `nbw` and `hubenv` use identical shelf naming for identical environments, and that the on-disk layout is consistent across both subsystems.

## Spec header field priority

| Field          | Header field      | Priority                                           |
|----------------|-------------------|----------------------------------------------------|
| `shelf_name`   | `shelf_name`      | 1) Header `shelf_name` → 2) `environment_name` → 3) `moniker` |
| `environment_name` | `environment_name` | 1) Header `environment_name` → 2) `kernel_name` (with `python3` → `base`) → 3) `image_name` |
| `display_name` | `display_name`    | 1) Header `display_name` → 2) `kernel_name` → 3) `None` |
| `kernel_name`  | `kernel_name`     | 1) Header `kernel_name` → 2) inline mamba `name` → 3) compiled output → 4) `None` |

## Backward compatibility

The `shelf_name` fallback to `moniker` (derived from `image_name`) preserves
backward compatibility with existing pantry directories where `kernel_name`
differs from `image_name`.  New specs or updated specs may set an explicit
`shelf_name` header field to control the directory name directly.