# Release Checklist for ai-protocol-mock

## 1. Create GitHub Repository

Create `hiddenpath/ai-protocol-mock` on GitHub:

- **Option A**: Via GitHub web UI
  1. Go to https://github.com/new
  2. Repository name: `ai-protocol-mock`
  3. Owner: `hiddenpath`
  4. Description: `Unified mock server for AI-Protocol runtimes - HTTP provider and MCP JSON-RPC mocking`
  5. Public, no README (we have one)
  6. Add LICENSE: choose "Add a license" → MIT (we also include Apache-2.0 in dual license)

- **Option B**: Via GitHub CLI
  ```bash
  gh repo create hiddenpath/ai-protocol-mock --public --description "Unified mock server for AI-Protocol runtimes" --clone=false
  ```

## 2. Initialize Git and Push

```powershell
cd D:\rustapp\ai-protocol-mock
git init
git add .
git commit -m "Initial release v0.1.0"
git branch -M main
git remote add origin https://github.com/hiddenpath/ai-protocol-mock.git
git push -u origin main
```

## 3. Create Release Tag

```powershell
git tag -a v0.1.0 -m "Release v0.1.0"
git push origin v0.1.0
```

## 4. Create GitHub Release

- Go to https://github.com/hiddenpath/ai-protocol-mock/releases/new
- Tag: v0.1.0
- Title: v0.1.0
- Description: First release. HTTP mock (OpenAI + Anthropic), MCP JSON-RPC mock, Docker support.

## 5. Publish to PyPI (optional)

ai-protocol-mock is a dev/testing tool. If you want to publish:

```powershell
pip install build twine
python -m build
twine upload dist/*
```

---

## Other Repos - Push & Release

### ai-protocol (v0.7.1)
```powershell
cd D:\ai-protocol
git add .
git commit -m "Release v0.7.1"
git tag -a v0.7.1 -m "Release v0.7.1"
git push origin main
git push origin v0.7.1
```

### ai-lib-rust (v0.8.1)
```powershell
cd D:\rustapp\ai-lib-rust
git add .
git commit -m "Release v0.8.1"
git tag -a v0.8.1 -m "Release v0.8.1"
git push origin main
git push origin v0.8.1
# Publish to crates.io: cargo publish
```

### ai-lib-python (v0.7.1)
```powershell
cd D:\rustapp\ai-lib-python
git add .
git commit -m "Release v0.7.1"
git tag -a v0.7.1 -m "Release v0.7.1"
git push origin main
git push origin v0.7.1
# Publish to PyPI: python -m build && twine upload dist/*
```

### ailib.info
```powershell
cd D:\rustapp\ailib.info
git add .
git commit -m "Update versions: 0.7.1, 0.8.1 and add ai-protocol-mock"
git push origin main
```
