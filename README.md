# Chromium Patcher

A tool to manage patches for submodules in Chromium-based project.

## Features

- Apply patches to multiple sub-repos
- Generate patches from modified files
- Automatic validate patch status with `.patchinfo` files to decide to apply patches.

## Usage

1. Configure paths in `config.py`:
   - `CHROMIUM_SRC_DIR`: Path to your Chromium source
   - `PATCHES_DIR`: Where patches are stored
   - `REPO_DIRS`: List of submodules that you want to patch

2. Run commands:
   ```bash
   # For applying patches
   python main.py apply_patches

   # Generate patches from changes
   # 1. make some changes in the submodule X
   # 2. Remember to add X (relative path) to `REPO_DIRS` in `config.py`
   # 3. generate
   python main.py generate_patches

   # Show help
   python main.py --help
   ```

## How It Works

### Applying Patches

1. Iterate `.patch` files in `PATCHES_DIR` (see [`config.py`](./config.py)) <br>
Check if there is corresponding `.patchinfo` file:
    1. no? => New `.patch` file => Add to `TO_PATCH` list
    2. yes? check hash of `.patch` file and each affected file. 
        1. different? add to `TO_PATCH` list.
        2. otherwise, no need to patch

2. Iterate `.patchinfo` files in `PATCHES_DIR` (see [`config.py`](./config.py)) <br>
Check if there is corresponding `.patch` file:
    1. yes? skip, this `.patch` file is still used in the project, do nothing
    2. no? this `.patch` file is obsoleted, need to restore all affected files => add to `TO_RESET`

3. Iterate `TO_PATCH` list:
    1. reset all affected files
    2. apply patch
    3. create or update `.patchinfo` file

4. Iterate `TO_RESET` list:
    1. reset all affected files
    2. delete `.patchinfo` file

### Generating Patches

1. For each submodule in `REPO_DIRS`:
   - Get list of modified files using `git diff`
   - Filter out submodules and untracked files
   - Only include files with actual changes

2. For each modified file:
   - Generate patch using `git diff` with full index
   - Convert file path to patch filename (e.g., `base/win/file.cc` -> `base-win-file.cc.patch`)
   - Save patch to corresponding directory in `PATCHES_DIR`

3. Handle existing patches:
   - Keep patches listed in `patch_files_to_keep`
   - Remove stale patch files that are no longer needed

