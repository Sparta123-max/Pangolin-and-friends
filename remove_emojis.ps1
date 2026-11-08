$files = @(
    'templates\index.html',
    'templates\about.html',
    'templates\login.html',
    'templates\TeTe_game\index.html'
)

# List of emoji patterns to remove (as Unicode escape sequences)
$emojiPatterns = @(
    "\u{1F332}", "\u{1F33F}", "\u{1F343}", "\u{1F331}",
    "\u{1F994}", "\u26A0\u{FE0F}", "\u{1F5D1}\u{FE0F}", "\u{1F4E1}",
    "\u23F1\u{FE0F}", "\u{1F3A5}", "\u{1F43E}", "\u{1F3AE}",
    "\u{1F5FA}\u{FE0F}", "\u{1F4F7}", "\u{1F4CA}", "\u{1F39E}\u{FE0F}",
    "\u{1F91D}", "\u{1F3AF}", "\u{1F4EC}", "\u{1F4AC}",
    "\u2709\u{FE0F}", "\u{1F4CD}", "\u26A1", "\u{1F4DA}",
    "\u{1F4BB}", "\u{1F392}", "\u23F3", "\u{1F511}",
    "\u{1F3AE}", "\u{1F4F0}"
)

foreach ($file in $files) {
    $content = [System.IO.File]::ReadAllText($file, [System.Text.Encoding]::UTF8)
    
    # Remove common nature/UI emojis by character range
    # Remove emoji using regex for common emoji ranges
    $content = [System.Text.RegularExpressions.Regex]::Replace($content, '[\u{1F300}-\u{1F9FF}]', '', [System.Text.RegularExpressions.RegexOptions]::None)
    $content = [System.Text.RegularExpressions.Regex]::Replace($content, '[\u{2600}-\u{27BF}][\uFE0F]?', '', [System.Text.RegularExpressions.RegexOptions]::None)
    $content = [System.Text.RegularExpressions.Regex]::Replace($content, '[\u23E9-\u23FA][\uFE0F]?', '', [System.Text.RegularExpressions.RegexOptions]::None)
    $content = [System.Text.RegularExpressions.Regex]::Replace($content, '[\u25AA-\u25FE][\uFE0F]?', '', [System.Text.RegularExpressions.RegexOptions]::None)
    $content = [System.Text.RegularExpressions.Regex]::Replace($content, '[\u2B50-\u2B55][\uFE0F]?', '', [System.Text.RegularExpressions.RegexOptions]::None)
    
    # Clean up extra spaces in HTML text content (not in CSS)
    # Fix "> " -> ">" for obvious double-spaces in button/div text
    
    [System.IO.File]::WriteAllText($file, $content, [System.Text.Encoding]::UTF8)
    Write-Host "Processed: $file"
}
Write-Host "Done!"
