"""Gera pacotes standalone do Gerenciador de Fotos de Pessoal.

Execute este script no próprio sistema de destino. O Nuitka não faz
cross-compilation entre Windows e macOS.
"""

import importlib.util
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path


APP_NAME = "Gerenciador de Fotos de Pessoal"
EXECUTABLE_NAME = "GerenciadorFotos"
BUILD_DEPENDENCIES = {
    "nuitka": "Nuitka",
    "ordered_set": "ordered-set",
}


def _optional_icon(base_dir: Path, filenames: tuple[str, ...]) -> Path | None:
    candidates = tuple(
        directory / filename
        for filename in filenames
        for directory in (base_dir, base_dir / "packaging")
    )
    return next((path for path in candidates if path.is_file()), None)


def _run(command: list[str], cwd: Path) -> None:
    print("\nComando de compilação:\n  " + " ".join(command))
    subprocess.run(command, cwd=cwd, check=True)


def _package_windows(output_dir: Path) -> None:
    dist_candidates = (
        output_dir / f"{EXECUTABLE_NAME}.dist",
        output_dir / "main.dist",
    )
    dist_dir = next((path for path in dist_candidates if path.is_dir()), None)
    if dist_dir is None:
        print("⚠️  Diretório .dist não encontrado; o ZIP não pôde ser criado.")
        return
    archive_base = output_dir / f"{EXECUTABLE_NAME}-Windows"
    archive = Path(shutil.make_archive(str(archive_base), "zip", dist_dir))
    print(f"✅ Pacote Windows criado: {archive}")


def _package_macos(base_dir: Path, output_dir: Path) -> None:
    app_candidates = (
        output_dir / f"{APP_NAME}.app",
        output_dir / f"{EXECUTABLE_NAME}.app",
        output_dir / "main.app",
    )
    app_path = next((path for path in app_candidates if path.is_dir()), None)
    if app_path is None:
        print("⚠️  Bundle .app não encontrado; o DMG não pôde ser criado.")
        return

    staging_dir = output_dir / "dmg-content"
    if staging_dir.exists():
        shutil.rmtree(staging_dir)
    staging_dir.mkdir(parents=True)
    shutil.copytree(app_path, staging_dir / app_path.name, symlinks=True)
    os.symlink("/Applications", staging_dir / "Applications")

    dmg_path = base_dir / "build" / f"{EXECUTABLE_NAME}-macOS.dmg"
    subprocess.run(
        [
            "hdiutil",
            "create",
            "-volname",
            APP_NAME,
            "-srcfolder",
            str(staging_dir),
            "-ov",
            "-format",
            "UDZO",
            str(dmg_path),
        ],
        cwd=base_dir,
        check=True,
    )
    shutil.rmtree(staging_dir)
    print(f"✅ Instalador macOS criado: {dmg_path}")


def build_app() -> int:
    system = platform.system()
    if system not in {"Windows", "Darwin"}:
        print(
            "❌ Este script deve ser executado no Windows ou no macOS. "
            "Para Linux, use o manifesto Flatpak."
        )
        return 2
    missing_dependencies = [
        package_name
        for module_name, package_name in BUILD_DEPENDENCIES.items()
        if importlib.util.find_spec(module_name) is None
    ]
    if missing_dependencies:
        packages = " ".join(missing_dependencies)
        print(
            "❌ Dependências de compilação ausentes: "
            f"{', '.join(missing_dependencies)}. Execute:\n"
            f'   "{sys.executable}" -m pip install -U {packages}'
        )
        return 2

    base_dir = Path(__file__).resolve().parent
    main_file = base_dir / "main.py"
    output_dir = base_dir / "build" / f"nuitka-{system.casefold()}"
    output_dir.mkdir(parents=True, exist_ok=True)

    command = [
        sys.executable,
        "-m",
        "nuitka",
        "--standalone",
        "--enable-plugin=pyside6",
        "--include-qt-plugins=imageformats,platforms,styles",
        "--include-package=core",
        "--include-package=ui",
        # Mantém os codecs disponíveis mesmo em ambientes Python mínimos.
        "--include-module=encodings",
        "--follow-imports",
        "--clang",
        "--lto=no",
        f"--jobs={max(1, os.cpu_count() or 1)}",
        "--show-progress",
        "--assume-yes-for-downloads",
        "--remove-output",
        f"--output-dir={output_dir}",
        f"--output-filename={EXECUTABLE_NAME}",
    ]

    if system == "Windows":
        command.append("--windows-console-mode=disable")
        # Prefere o formato nativo para não depender do imageio na conversão.
        icon = _optional_icon(base_dir, ("icone.ico", "icone.png"))
        if icon:
            command.append(f"--windows-icon-from-ico={icon}")
            print(f"🎨 Ícone do Windows: {icon}")
    else:
        command.extend(
            (
                "--macos-create-app-bundle",
                "--macos-app-mode=gui",
                "--static-libpython=no",
            )
        )
        icon = _optional_icon(base_dir, ("icone.icns", "icone.png"))
        if icon:
            command.append(f"--macos-app-icon={icon}")
            print(f"🎨 Ícone do macOS: {icon}")

    command.append(str(main_file))
    print(f"🚀 Compilando {APP_NAME} para {system}...")
    try:
        _run(command, base_dir)
        if system == "Windows":
            _package_windows(output_dir)
        else:
            _package_macos(base_dir, output_dir)
    except (OSError, subprocess.CalledProcessError) as exc:
        print(f"❌ Falha durante a compilação ou empacotamento: {exc}")
        return 1

    print("✅ Processo concluído.")
    return 0


if __name__ == "__main__":
    raise SystemExit(build_app())
