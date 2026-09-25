from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tests.helpers import REPO_ROOT


def test_controlfix_cli_regression_fixture_preserves_tokens_and_layout(tmp_path):
    output_path = tmp_path / "controlfixed.json"
    report_path = tmp_path / "report.json"

    subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "004_controlfix_translations.py"),
            str(REPO_ROOT / "tests/fixtures/controlfix_input.json"),
            "-o",
            str(output_path),
            "--source",
            str(REPO_ROOT / "tests/fixtures/controlfix_source.json"),
            "--report",
            str(report_path),
            "--wrap-width",
            "18",
        ],
        check=True,
        cwd=REPO_ROOT,
    )

    data = json.loads(output_path.read_text(encoding="utf-8"))
    by_id = {entry["id"]: entry for entry in data["entries"]}

    assert by_id["scr_token_layout"]["translated"].startswith("[black]Ciao [player]!")
    assert "\n" in by_id["scr_token_layout"]["translated"]
    assert by_id["tbl_menu_yes_no"]["translated"] == "Sì\nNo"
    assert by_id["tbl_battle_messages_00412_3FE6D5"]["translated"] == "Cosa farà\n\\\\12?"

    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["stats"]["remaining_control_mismatches"] == 0
    assert report["stats"]["menu_line_break_repairs"] == 1
    assert report["stats"]["battle_prompt_layout_repairs"] == 1


def test_controlfix_cli_wraps_japanese_and_adds_page_controls(tmp_path):
    input_path = tmp_path / "ja-input.json"
    source_path = tmp_path / "ja-source.json"
    output_path = tmp_path / "ja-output.json"
    report_path = tmp_path / "ja-report.json"
    input_path.write_text(
        json.dumps(
            {
                "entries": [
                    {
                        "id": "scr_ja_test",
                        "category": "scripts",
                        "original": "Choose a character.",
                        "translated": "あいうえおかきくけこさしすせそ",
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    source_path.write_text(
        json.dumps(
            {
                "entries": [
                    {
                        "id": "scr_ja_test",
                        "category": "scripts",
                        "original": "Choose a character.",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "004_controlfix_translations.py"),
            str(input_path),
            "-o",
            str(output_path),
            "--source",
            str(source_path),
            "--report",
            str(report_path),
            "--target-lang",
            "ja",
            "--wrap-width",
            "6",
        ],
        check=True,
        cwd=REPO_ROOT,
    )

    entry = json.loads(output_path.read_text(encoding="utf-8"))["entries"][0]
    assert entry["translated"] == (
        "[japanese]あいうえおか\nきくけこさし\\lすせそ[latin]"
    )
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["stats"]["remaining_control_mismatches"] == 0
    assert report["stats"]["japanese_page_controls"] == 1

    second_output = tmp_path / "ja-second.json"
    second_report = tmp_path / "ja-second-report.json"
    subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "004_controlfix_translations.py"),
            str(output_path),
            "-o",
            str(second_output),
            "--source",
            str(source_path),
            "--report",
            str(second_report),
            "--target-lang",
            "ja",
            "--wrap-width",
            "6",
        ],
        check=True,
        cwd=REPO_ROOT,
    )
    assert json.loads(second_output.read_text(encoding="utf-8")) == json.loads(
        output_path.read_text(encoding="utf-8")
    )
    second_stats = json.loads(second_report.read_text(encoding="utf-8"))["stats"]
    assert second_stats["remaining_control_mismatches"] == 0


def test_controlfix_japanese_wakachigaki_and_buffer_are_byte_idempotent(tmp_path):
    source_path = tmp_path / "source.json"
    input_path = tmp_path / "input.json"
    first_path = tmp_path / "first.json"
    second_path = tmp_path / "second.json"
    source_path.write_text(json.dumps({"entries": [
        {"id": "script", "category": "scripts", "original": "Hello [buffer1]."}
    ]}), encoding="utf-8")
    input_path.write_text(json.dumps({"entries": [
        {"id": "script", "category": "scripts", "original": "Hello [buffer1].",
         "translated": "あいうえお。 かき [buffer1] くけこ！ さしす"}
    ]}, ensure_ascii=False), encoding="utf-8")

    for input_file, output_file in ((input_path, first_path), (first_path, second_path)):
        subprocess.run([
            sys.executable, str(REPO_ROOT / "004_controlfix_translations.py"),
            str(input_file), "-o", str(output_file), "--source", str(source_path),
            "--target-lang", "ja", "--wrap-width", "8",
        ], check=True, cwd=REPO_ROOT)

    assert first_path.read_bytes() == second_path.read_bytes()
    text = json.loads(first_path.read_text(encoding="utf-8"))["entries"][0]["translated"]
    assert "[latin][buffer1][japanese]" in text
    assert not any(fragment in text for fragment in (" \n", "\n ", " \\l", "\\l ", " \\p", "\\p "))


def test_japanese_reordered_leading_buffer_is_not_duplicated(tmp_path):
    source = {"entries": [{"id": "reordered", "category": "menu_common",
                           "original": '"[buffer1] could not be found nearby.\\nTry elsewhere!"'}]}
    reviewed = {"entries": [{**source["entries"][0],
                             "translated": "ちかくに [buffer1]は いないようだ。 ちがう ばしょを さがしてみよう！"}]}
    source_path = tmp_path / "source.json"
    input_path = tmp_path / "reviewed.json"
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"
    source_path.write_text(json.dumps(source, ensure_ascii=False), encoding="utf-8")
    input_path.write_text(json.dumps(reviewed, ensure_ascii=False), encoding="utf-8")
    for inp, out in ((input_path, first), (first, second)):
        subprocess.run([sys.executable, str(REPO_ROOT / "004_controlfix_translations.py"),
                        str(inp), "-o", str(out), "--source", str(source_path),
                        "--target-lang", "ja"], cwd=REPO_ROOT, check=True,
                       stdout=subprocess.DEVNULL)
    text = json.loads(first.read_text(encoding="utf-8"))["entries"][0]["translated"]
    assert text.count("[buffer1]") == 1
    assert first.read_bytes() == second.read_bytes()
