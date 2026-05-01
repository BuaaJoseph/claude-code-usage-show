# Homebrew Cask for Claude Code Usage
#
# To use this cask, create a personal Homebrew tap:
#   1. Create a GitHub repo named "homebrew-tap"
#   2. Copy this file to Casks/claude-code-usage.rb in that repo
#   3. Users install with: brew install --cask <your-github>/tap/claude-code-usage
#
# Or install directly from the formula URL:
#   brew install --cask /path/to/claude-code-usage.rb

cask "claude-code-usage" do
  version "1.0.1"
  sha256 :no_check # Update with actual SHA256 after uploading DMG

  url "https://github.com/BuaaJoseph/claude-code-usage-show/releases/download/v#{version}/Claude-Code-Usage-#{version}.dmg"
  name "Claude Code Usage"
  desc "Dashboard to visualize Claude Code CLI usage statistics"
  homepage "https://github.com/BuaaJoseph/claude-code-usage-show"

  app "Claude Code Usage.app"

  zap trash: [
    "~/Library/Caches/com.buaajoseph.claude-code-usage",
    "~/Library/Preferences/com.buaajoseph.claude-code-usage.plist",
  ]
end
