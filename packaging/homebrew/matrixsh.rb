# Homebrew formula TEMPLATE for MatrixShell (matrixsh)
#
# To publish, create a Homebrew tap repo and place this formula there.
# Update: homepage, url, sha256, version.
class Matrixsh < Formula
  desc "MatrixShell: AI-augmented shell wrapper powered by MatrixLLM"
  homepage "https://example.com"
  url "https://example.com/matrixsh-0.3.0.tar.gz"
  sha256 "PUT_SHA256_HERE"
  license "Apache-2.0"

  depends_on "python@3.11"

  def install
    system "python3", "-m", "pip", "install", ".", "--prefix", prefix
    bin.install_symlink prefix/"bin/matrixsh"
  end

  test do
    system "#{bin}/matrixsh", "--help"
  end
end
