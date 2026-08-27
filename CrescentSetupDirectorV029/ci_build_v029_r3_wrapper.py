from __future__ import annotations
import ci_build_v029 as ci

_original_patch = ci.apply_r3_source_patch

def apply_r3_source_patch_fixed() -> None:
    _original_patch()
    path = ci.SOURCE / 'CrescentSetupDirector.csproj'
    text = path.read_text(encoding='utf-8')
    incomplete = 'CEは40秒前にRSR/BMRを完全停止し、風水士で停止します。'
    complete = 'CEは40秒前にRSR/BMRを完全停止し、風水士でたたかいのベル・いこいのベルを使って吟遊詩人で待機します。'
    if incomplete in text:
        text = text.replace(incomplete, complete)
        path.write_text(text, encoding='utf-8', newline='\n')
    elif complete not in text:
        raise SystemExit('R3 complete CE bell description was not found')

ci.apply_r3_source_patch = apply_r3_source_patch_fixed
ci.main()
