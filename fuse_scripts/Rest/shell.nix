{ pkgs ? import <nixpkgs> {} }:
pkgs.mkShell {
  packages = [
    (pkgs.python311.withPackages (ps: [
      ps.isort
      ps.black
      ps.flake8
      ps.pylint
      
      ps.sphinx
      
      ps.fusepy
      ps.magic
    ]))
    pkgs.zsh
  ];
}
