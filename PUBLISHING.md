# Publishing this repo on GitHub

## 1. Pre-publish checklist

Verify no server-specific paths remain:
```bash
grep -rn '/data6\|snuintern2\|folder\|Madgraph\|madgraph' --exclude-dir=.git \
    README.md run_signal.sh scripts/ condor/ cards/ .gitignore
```
This should return no results (Condor log files are OK to ignore).

Check that the MG5-generated `output/` directory is something you want to
include. It is large and contains auto-generated Fortran code. If you want
a lightweight repo, add `output/` to `.gitignore` and remove it from
tracking:
```bash
echo "output/" >> .gitignore
git rm -r --cached output/
```

## 2. Create a GitHub repository

Go to https://github.com/new and create a new repository:
- **Name**: e.g. `madgraph-mc-tutorial`
- **Visibility**: Public (or Private)
- Do **not** initialize with README, .gitignore, or license (you already have these locally)

## 3. Push to GitHub

```bash
cd /path/to/this/repo

# Stage all current changes
git add -A
git status   # review what will be committed

# Commit
git commit -m "Clean up paths for public release"

# Add the remote and push
git remote add origin git@github.com:<YOUR_USERNAME>/madgraph-mc-tutorial.git
git branch -M main
git push -u origin main
```

If using HTTPS instead of SSH:
```bash
git remote add origin https://github.com/<YOUR_USERNAME>/madgraph-mc-tutorial.git
```

## 4. Verify

After pushing, check the repo on GitHub:
- README.md should render cleanly with no server-specific paths
- No `/data6/...` or `snuintern2` references visible in source files
- Scripts reference `MG5_ROOT` env var and relative paths

## 5. Optional: add a license

If you want others to reuse this tutorial freely:
```bash
# MIT license (permissive, common for tutorials)
curl -sL https://opensource.org/licenses/MIT -o LICENSE
# Edit LICENSE to add your name and year, then:
git add LICENSE && git commit -m "Add MIT license"
git push
```

## 6. Optional: add a .gitattributes

To keep large binary files out of the repo history:
```bash
cat > .gitattributes << 'EOF'
*.root filter=lfs diff=lfs merge=lfs -text
*.pkl filter=lfs diff=lfs merge=lfs -text
*.gz filter=lfs diff=lfs merge=lfs -text
EOF
git add .gitattributes && git commit -m "Add .gitattributes for LFS"
```
This requires [Git LFS](https://git-lfs.github.com/) to be installed
(`git lfs install`) before pushing any `.root` files.
