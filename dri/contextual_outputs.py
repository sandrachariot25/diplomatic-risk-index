"""One v0.2 artifact set; raw review fragments remain internal research only."""
import csv
import io
import json
import os
import re
from collections import Counter,defaultdict
from .paths import ROOT,write_generated
from .analytical_sample import digest
from .analytics_outputs import file_sha,runtime_manifest

def dump(value):return json.dumps(value,ensure_ascii=False,sort_keys=True,allow_nan=False)

def csv_text(rows):
    s=io.StringIO(newline='');w=csv.DictWriter(s,fieldnames=list(rows[0]));w.writeheader()
    w.writerows({k:dump(v) if isinstance(v,(dict,list)) else v for k,v in row.items()} for row in rows)
    return s.getvalue()

def merge_expert_fields(record,previous):
    if previous is None:return record
    annotated=any(previous.get(k) is not None for k in ('expert_direction','expert_intensity','expert_notes','expert_reviewer','expert_ownership','expert_target','expert_relevance'))
    if previous['input_text_sha256']!=record['input_text_sha256'] or previous['rules_sha256']!=record['rules_sha256']:
        if annotated:raise ValueError('Expert annotation snapshot changed; preserve and reconcile it explicitly')
    else:
        for key in record:
            if key.startswith('expert_'):record[key]=previous.get(key,record[key])
    return record

def select_review(units,private,config,rules_sha):
    included=[u for u in units if not u['exclusion_reason']]
    rank=lambda u:digest([config['sampling_seed'],u['unit_id'],u['input_text_sha256']])
    groups=defaultdict(list)
    for u in included:groups[(u['source_id'],u['text_form'],u['direction'])].append(u)
    chosen={}
    for key,us in sorted(groups.items()):
        for u in sorted(us,key=rank)[:config['review_sample_per_stratum']]:chosen[u['unit_id']]=u
    for year in range(2015,2027):
        if not any(u['date'].startswith(str(year)) for u in chosen.values()):
            candidates=[u for u in included if u['date'].startswith(str(year))]
            if candidates:
                u=min(candidates,key=rank);chosen[u['unit_id']]=u
    old_path=ROOT/'data/dri_v02_review.json'
    old=json.loads(old_path.read_text(encoding='utf-8')) if old_path.exists() else {'records':[]}
    old_by_id={r['unit_id']:r for r in old['records']}
    if any(r['unit_id'] not in chosen and any(r.get(k) is not None for k in ('expert_direction','expert_intensity','expert_notes','expert_reviewer','expert_ownership','expert_target','expert_relevance')) for r in old['records']):
        raise ValueError('A completed expert record would leave the sample; preserve and reconcile it explicitly')
    records=[]
    for u in sorted(chosen.values(),key=lambda u:u['unit_id']):
        fragments=[]
        for fi,f in enumerate(private[u['unit_id']]):
            from .tokenization import prepare
            text=prepare(f['text']);es=[e for e in u['evidence'] if e['fragment_index']==fi]
            # Include beginning plus contexts of matched predicates; bounded internal
            # windows are for review, never falsely described as the whole speech.
            windows={(0,min(len(text),600))}
            for e in es:windows.add((max(0,e['char_start']-140),min(len(text),e['char_end']+140)))
            for a,b in sorted(windows):
                fragments.append({'fragment_index':fi,'source_ref':f['ref'],'window_start':a,'window_end':b,
                                  'text':text[a:b],'whole_fragment':a==0 and b==len(text)})
        rec={k:u[k] for k in ('unit_id','statement_ids','date','date_basis','country','target_country','language','source_id',
             'institution','institution_type','speaker_name','speaker_office','text_form','source_urls','input_text_sha256','direction','intensity','classification_status',
             'classification_reason','confidence','context_flags','discourse_roles','negation_present','quotation_present','historical_context_present','evidence')}
        rec.update(rules_sha256=rules_sha,fragments=fragments,expert_direction=None,expert_intensity=None,
            expert_ownership=None,expert_target=None,expert_relevance=None,expert_notes=None,expert_reviewer=None,expert_status='pending')
        records.append(merge_expert_fields(rec,old_by_id.get(u['unit_id'])))
    return {'model':'DRI v0.2','publication_policy':'internal_research_only',
        'sampling':'2 per source x text-form x proposed direction, plus missing years; deterministic SHA order; enriched review sample, not prevalence sample',
        'independent_expert_validation':False,'accuracy_established':False,'records':records}

def plot(result):
    os.environ['MPLCONFIGDIR']=str(ROOT/'.venv/matplotlib-cache')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import numpy as np
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':9,'axes.grid':True,'grid.alpha':.2})
    fig,axes=plt.subplots(4,1,figsize=(14,13),sharex=True)
    for ax,scope in zip(axes[:3],('pooled_sample','ROK','JPN')):
        rows=[r for r in result['monthly'] if r['scope']==scope];x=np.arange(len(rows))
        values=np.array([r['observed_intensity_0_3'] if r['observed_intensity_0_3'] is not None else np.nan for r in rows])
        ax.plot(x,values,color='#24617f',alpha=.55,lw=.8)
        low=[i for i,r in enumerate(rows) if r['observed_intensity_0_3'] is not None and not r['coverage_supported']]
        ok=[i for i,r in enumerate(rows) if r['coverage_supported']]
        ax.scatter(x[low],values[low],s=25,facecolors='none',edgecolors='#24617f',label='Недостаточное покрытие')
        ax.scatter(x[ok],values[ok],s=25,color='#24617f',label='Операционный порог пройден')
        ax.set_ylim(-.12,3.15);ax.set_yticks([0,1,2,3]);ax.set_ylabel('Интенсивность 0–3')
        ax.set_title(scope+' — среднее только классифицированных высказываний',loc='left');ax.legend(loc='upper right',fontsize=8)
        if scope=='pooled_sample':
            lower=[r['abstention_only_lower_bound'] if r['available_units'] else np.nan for r in rows]
            upper=[r['abstention_only_upper_bound'] if r['available_units'] else np.nan for r in rows]
            ax.fill_between(x,lower,upper,color='#e6b76c',alpha=.22,label='Границы из-за неопределённых случаев')
            ax.legend(loc='upper right',fontsize=8)
    rows=[r for r in result['monthly'] if r['scope']=='pooled_sample'];x=np.arange(len(rows))
    for key,color,label in [('available_units','#abbec5','Доступны'),('classified_units','#24617f','Классифицированы')]:
        axes[3].bar(x,[r[key] for r in rows],color=color,label=label,width=.8)
    axes[3].set_ylabel('Высказывания');axes[3].set_title('Объём покрытия: отсутствие классификации не является нейтральностью',loc='left');axes[3].legend()
    ticks=[i for i,r in enumerate(rows) if r['month'].endswith('-01')]
    axes[3].set_xticks(ticks,[rows[i]['month'][:4] for i in ticks]);axes[3].set_xlim(-1,len(rows))
    fig.suptitle('DRI v0.2 — экспериментальная контекстная оценка\nШкала риторики, не вероятность конфликта; независимая экспертная точность не установлена',fontsize=14)
    fig.text(.5,.012,'Пропуски сохранены. Заливка — арифметические границы для неопределённых единиц, не доверительный интервал.',ha='center',fontsize=9)
    fig.tight_layout(rect=(0,.03,1,.94));fig.savefig(ROOT/'docs/DRI_v02.png',dpi=150);plt.close(fig)

def replace_section(path,text):
    start='<!-- DRI_V02_START -->';end='<!-- DRI_V02_END -->';p=ROOT/path
    old=p.read_text(encoding='utf-8');old=re.sub(re.escape(start)+'.*?'+re.escape(end),'',old,flags=re.S).rstrip()
    write_generated(p,old+'\n\n'+start+'\n'+text+'\n'+end+'\n')

def write_v02(result,private,comparison,config,rules,reproduced):
    review=select_review(result['units'],private,config,digest(rules))
    runtime=runtime_manifest()
    write_generated(ROOT/'data/dri_v02_units.jsonl',''.join(dump(u)+'\n' for u in result['units']))
    write_generated(ROOT/'data/dri_v02_monthly.csv',csv_text(result['monthly']))
    write_generated(ROOT/'data/dri_v02_comparison.csv',csv_text(comparison))
    write_generated(ROOT/'data/dri_v02_review.json',json.dumps(review,ensure_ascii=False,indent=2,sort_keys=True)+'\n')
    plot(result)
    code=['dri/contextual.py','dri/contextual_index.py','dri/contextual_outputs.py','scripts/calculate_dri_v02.py',
          'dri/analytical_sample.py','dri/rhetoric.py','dri/tokenization.py','dri/connectors/assembly_pdf.py','dri/connectors/korea.py','dri/html.py','dri/identity.py',
          'dri/analytics.py','dri/analytics_outputs.py','dri/paths.py']
    manifest={'model':'DRI v0.2','config':config,'rules_sha256':digest(rules),'runtime':runtime,
        'code_sha256':{p:file_sha(ROOT/p) for p in code},'result_sha256':digest(result),
        'v01_manifest_sha256':file_sha(ROOT/'data/dri_v01_manifest.json'),
        'database_file_sha256':file_sha(ROOT/'data/dri.sqlite3'),
        'test_report_sha256':file_sha(ROOT/'docs/TEST_RESULTS.txt'),
        'preserved_v01_sha256':{str(p.relative_to(ROOT)):file_sha(p) for p in sorted(list((ROOT/'data').glob('dri_v01_*'))+list((ROOT/'docs').glob('DRI_v01*.png')))},
        'summary':result['summary'],'same_snapshot_recalculation_identical':reproduced,
        'review_sample_units':len(review['records']),'review_accuracy_established':False,
        'outputs_sha256':{p:file_sha(ROOT/p) for p in ['data/dri_v02_units.jsonl','data/dri_v02_monthly.csv','data/dri_v02_comparison.csv','docs/DRI_v02.png']},
        'internal_outputs_sha256':{'data/dri_v02_review.json':file_sha(ROOT/'data/dri_v02_review.json')}}
    write_generated(ROOT/'data/dri_v02_manifest.json',json.dumps(manifest,ensure_ascii=False,indent=2,sort_keys=True)+'\n')
    docs(result,comparison,manifest)

def docs(result,comparison,manifest):
    s=result['summary'];included=[u for u in result['units'] if not u['exclusion_reason']]
    sensitivity_keys=('without_source:kokkai_jp','without_source:mofa_kr','without_source:assembly_kr',
        'without_institution_type:parliament','without_institution_type:foreign_ministry',
        'without_selection_theme:historical_disputes','without_selection_theme:territorial_disputes','without_selection_theme:security')
    sensitivity_lines=[]
    pooled=[r for r in result['monthly'] if r['scope']=='pooled_sample' and r['dri_v02'] is not None]
    for key in sensitivity_keys:
        pairs=[(r,r['sensitivity'][key]) for r in pooled if key in r['sensitivity']]
        diffs=[abs(r['dri_v02']-v['observed_intensity_0_3']) for r,v in pairs if v['observed_intensity_0_3'] is not None]
        lost=sum(v['observed_intensity_0_3'] is None for r,v in pairs)
        sensitivity_lines.append(f'| {key} | {len(diffs)} | {max(diffs):.3f} | {lost} |' if diffs else f'| {key} | 0 | — | {lost} |')
    lines=['## DRI v0.2 — контекстная оценка высказываний', '',
        'Экспериментальные воспроизводимые эвристики EN/KO/JA. Это не экспертная разметка, не вероятность кризиса и не историческая валидация. v0.1, база и исходные тексты сохранены. Внешних моделей, сети, новых зависимостей и массового сбора нет.', '',
        f'Из {s["available_units"]} доступных единиц автоматически классифицировано {s["classified_units"]} ({100*s["automatically_classified_share"]:.1f}%); требуют проверки {s["needs_review_units"]} ({100*(1-s["automatically_classified_share"]):.1f}%). Ранее исключённые {s["excluded_units"]} записей остаются исключены. Направленности: `{s["directions"]}`. Интенсивности классифицированных: `{s["intensities"]}`.', '',
        f'Полнота доступных единиц: {s["full_units"]} полных / {s["partial_units"]} фрагментарных; из них классифицированы {s["classified_full_units"]} полных / {s["classified_partial_units"]} фрагментарных. Это сохранённые признаки, новая диагностика полноты не проводилась.', '',
        '### Единица и правила', '',
        'Одна датированная единица автора/эпизода с прежними statement_ids, источниками и атрибуцией. Цитатные блоки не являются независимыми голосами. Даты/выступления не объединяются по сходству. Короткая законченная реплика может получить интенсивность 3, длинная речь — 0; длина не входит в формулу. Из неполного текста вывод ограничен сохранённым материалом, а не смыслом всей речи.', '',
        'Правила в config/dri_v02_rules.json задают предикат и аргументную рамку, а не наличие изолированного слова. Общие ограничения проверяют адресата, чужого говорящего, цитату, отрицание возле предиката, вопрос/условность, историю и третью сторону. Кооперация РК–Япония по вопросу КНДР не отбрасывается только из-за упоминания третьей страны. Анафора ограничена одним соседним предложением внутри одного атрибутированного фрагмента. Границы предложений определяются до удаления CJK-пробелов PDF; позиции переводятся обратно в подготовленный текст. Непарная кавычка делает неопределённым только затронутый интервал, не все предшествующие предложения.', '',
        'Нейтральность требует собственной явной фактической дипломатической рамки. Отсутствие совпадения даёт undetermined/needs_review с intensity=null. При конкурирующих собственных кооперативных и конфронтационных позициях также needs_review. Направленности не следует трактовать как исчерпывающую оценку всей внешней политики.', '',
        'Шкала: 0 — нет выраженной конфронтации в подтверждённой нейтральной/кооперативной позиции; 1 — критическая оценка/обеспокоенность; 2 — протест/обвинение/требование; 3 — выраженный призыв к санкциям/прекращению сотрудничества/ограничительным мерам. Одно высказывание получает максимальную интенсивность среди поддержанных собственных рамок, а не сумму совпадений. Возможность обнаружить больше рамок в длинном тексте остаётся смещением полноты, хотя длина не является весом.', '',
        'confidence=bounded_rule_support_not_calibrated означает только выполнение формальных проверок. Это не вероятность правильности. Известные границы: ограниченное покрытие предикатов/словоформ, риторические вопросы, вложенная речь, сложная анафора, смешанная позиция и усечённый контекст. Простые рамки не заменяют семантический анализ эксперта.', '',
        '### Формула и покрытие', '',
        '`M[t] = sum(intensity[u] для rule_supported) / N_classified[t]`, исходная шкала 0–3. Каждая уникальная единица имеет один голос; источники/институты/длина не имеют весов. Кооперативные и нейтральные классифицированные единицы имеют 0; неопределённые не входят в знаменатель и не заменяются нулём.', '',
        'dri_v02 = observed_intensity_0_3 определён при хотя бы одном классифицированном высказывании, включая месяцы с малым объёмом. Надёжность не кодируется самим баллом: coverage_supported и measurement_status отдельно проверяют операционное покрытие (≥5 классифицированных и ≥50% доступных классифицировано). Для pooled_sample дополнительно требуется присутствие обеих стран среди классифицированных. Это диагностические пороги, не доказательство надёжности/точности. Пустой месяц и месяц без классификации имеют null. Сглаживания и шкалы 0–100 нет.', '',
        'Публикуются отдельные ряды РК, Японии и условный pooled_sample. Последний — среднее наблюдаемой выборки, подверженное её составу, а не равнопредставленный двусторонний дипломатический индекс. Страна, язык, институт и источник показаны отдельно. Даже прохождение порога не исправляет смещённый отбор.', '',
        'Одинаковая разметочная шкала задана для трёх языков, но её межъязыковая сопоставимость и эквивалентность переводов экспертно не подтверждены. Различия стран могут отражать различия правил, сохранённых текстов и их тематического отбора.', '',
        'Арифметические границы при неопределённых: lower=sum(I_known)/N_available, upper=(sum(I_known)+3*N_unknown)/N_available. Это возможный диапазон при неизвестных оценках, а не подстановка нулей и не доверительный интервал; ошибки самих эвристических меток он не учитывает.', '',
        f'Месяцев с числовой наблюдаемой оценкой: `{s["observed_months_by_scope"]}`; с операционным покрытием: `{s["supported_months_by_scope"]}`. Все 142 месяца 2015-01…2026-10 сохранены для каждого ряда.', '',
        '| Источник / страна / язык | Доступны | Классифицированы | needs_review | Конфронтационные | Кооперативные | Нейтральные |',
        '|---|---:|---:|---:|---:|---:|---:|']
    groups=defaultdict(list)
    for u in included:groups[(u['source_id'],u['country'],u['language'])].append(u)
    for key,us in sorted(groups.items()):
        cs=[u for u in us if u['classification_status']=='rule_supported']
        lines.append('| '+' / '.join(key)+f' | {len(us)} | {len(cs)} | {len(us)-len(cs)} | '+ ' | '.join(str(sum(u['direction']==d for u in cs)) for d in ('confrontational','cooperative','neutral'))+' |')
    lines += ['',f'Причины проверки: `{s["review_reasons"]}`.', '',
        '### Зависимость от состава и отбора', '',
        'В sensitivity каждой месячной строки повторяется та же формула после исключения каждого источника, типов институтов parliament/foreign_ministry/government/head_of_state_administration/unknown, а также historical_disputes, territorial_disputes и security по сохранённым меткам отбора. Новых индексов и весов при этом не вводится. Малый остаток/полное исчезновение классифицированных показаны явно. Метки theme — прежние эвристики, не независимая экспертная тематика; institution_type взят из statement_metadata, неизвестные не угаданы по месту заседания.', '',
        '| Исключение в pooled_sample | Месяцев с оставшейся оценкой | Максимальный абсолютный сдвиг на шкале 0–3 | Месяцев, где оценка исчезла |',
        '|---|---:|---:|---:|',*sensitivity_lines,'',
        'Сдвиги относятся к малым условным подвыборкам и не являются статистически подтверждёнными эффектами источника. Совместное исключение тем не устраняет смещение обнаружения: отсутствующих в базе нейтральных высказываний такой анализ не восстанавливает.', '',
        '907 из 1017 доступных единиц — японские парламентские фрагменты (89,2%). Комментарии МИД обнаруживались по институциональным заголовкам и часто конфликтной тематике; NDL — по 日韓 и прежним ограничениям ролей, с сохранением одного короткого предложения. Поэтому доля сигналов относится только к этому корпусу и к классифицируемой его части, а не ко всей дипломатической коммуникации. Правила тоже могут легче распознавать явный протест, чем нейтральную/кооперативную позицию: пропуск нельзя считать нейтральностью.', '',
        '### Отчёты МИД как контекст', '',
        f'Результат проверки связей: `{s["context_reports"]}`. Общие дата/тема — лишь possible_context, не подтверждённое тождество события. Такие связи сохранены для проверки и не добавляют текст, оценку или сигнал. Без подтверждённого события пересказ не подставляется в усечённую цитату. 341 отчёт не преобразован в новые заявления.', '',
        '### Внутренняя экспертная выборка', '',
        f'Сформировано {manifest["review_sample_units"]} единиц в data/dri_v02_review.json: стратификация по источнику, форме/полноте текста и предложенной направленности, затем дополнение отсутствующих лет; детерминированный SHA-порядок. Включены четыре источника, EN/KO/JA, полные/короткие тексты, разные годы и неопределённые случаи. Полные президентские речи и письменные брифинги образуют разные страты. Страты нейтральных/кооперативных заполняются только при наличии таких предложенных оценок; это обогащённая проверочная выборка, не оценка распространённости.', '',
        'Файл содержит внутренние окна исходного текста, смещения, предложенные оценки и пустые expert_* поля для независимого специалиста. Не включать файл в публичные выгрузки. Повторный запуск сохраняет введённые экспертные поля при том же снимке/правилах; при смене снимка с заполненной разметкой останавливается. Независимой разметки пока нет; precision, recall, accuracy и межэкспертное согласие не вычисляются.', '',
        '### Сравнение v0.1 / v0.2', '',
        'data/dri_v02_comparison.csv сопоставляет месяцы внутри прежних девяти страт: частоту выражений/1000 токенов и среднюю контекстную интенсивность 0–3 с разными знаменателями. Их числовая разность и корреляция не интерпретируются как улучшение. v0.1 остался побайтово неизменным. Исходные 24 ручные проверки v0.1 не повторялись и не служили экспертными метками v0.2.', '',
        'Глобальный запрет упоминания третьей стороны в v0.1 заменён локальной проверкой адресата предиката. Собственная отрицательная оценка может распознаваться без названия торговой меры, а нейтральное описание мер не получает высокий балл автоматически. v0.1 не давал семантической направленности; v0.2 также не трактует словарный ноль как нейтральность. Часть проблем анафоры, отрицания и чужой речи остаётся нерешённой. Эти программные изменения не доказывают превосходства классификации.', '',
        f'В {sum(r["available_units"]>0 and r["v01_rate_per_1000"]==0 and r["v02_confrontational_units"]>0 for r in comparison)} наблюдаемых компонент-месяцах v0.1 имел словарный ноль, а v0.2 нашёл хотя бы одну поддержанную конфронтационную рамку. Это различие измерений, не доказанная коррекция всех ошибок.', '',
        f'В сопоставлении прежних страт: порог v0.1 проходит {sum(r["v01_supported"] for r in comparison)} компонент-месяцев; критерии покрытия v0.2 — {sum(r["v02_coverage_supported"] for r in comparison)}; оба — {sum(r["v01_supported"] and r["v02_coverage_supported"] for r in comparison)}. Новая доля классифицируемости и прежний порог токенов измеряют разные ограничения, эти числа не являются сравнением точности.', '',
        '| Год | РК: доступно / классифицировано / конфронтационных | Япония: доступно / классифицировано / конфронтационных |',
        '|---|---|---|']
    for year in range(2015,2027):
        cells=[]
        for country in ('ROK','JPN'):
            us=[u for u in included if u['date'].startswith(str(year)) and u['country']==country]
            cells.append(f'{len(us)} / {sum(u["classification_status"]=="rule_supported" for u in us)} / {sum(u["direction"]=="confrontational" for u in us)}')
        lines.append(f'| {year} | '+ ' | '.join(cells)+' |')
    lines += ['',
        '### Воспроизведение и файлы', '',
        f'Результат SHA-256: {manifest["result_sha256"]}; повторный расчёт: {manifest["same_snapshot_recalculation_identical"]}. В manifest зафиксированы код, правила, параметры, входной снимок и хэши артефактов.', '',
        'Результаты автоматических проверок — в единственном docs/TEST_RESULTS.txt; его SHA-256 зафиксирован в manifest. Тесты проверяют программное поведение, а не экспертную точность политических меток.', '',
        'Команда: `.venv\\Scripts\\python.exe scripts/calculate_dri_v02.py --verify-reproducibility`. Тесты: `.venv\\Scripts\\python.exe scripts/run_tests.py`. Публично безопасные аналитические метаданные: data/dri_v02_units.jsonl, data/dri_v02_monthly.csv, data/dri_v02_comparison.csv, data/dri_v02_manifest.json; график docs/DRI_v02.png. Внутренний файл с текстами — только data/dri_v02_review.json.']
    replace_section('docs/QUALITY_REPORT.md','\n'.join(lines))
    replace_section('README.md','## DRI v0.2\n\nОфлайн-контекстные правила EN/KO/JA: `.venv\\Scripts\\python.exe scripts/calculate_dri_v02.py --verify-reproducibility`. '
        'Формула — средняя интенсивность 0–3 среди классифицированных высказываний; неизвестные не равны нейтральным. '
        'Это экспериментальная оценка риторики, не прогноз; экспертная точность не установлена. '
        'Метод и ограничения — docs/QUALITY_REPORT.md; правила — config/dri_v02_rules.json. '
        '**data/dri_v02_review.json содержит внутренние исходные фрагменты и не предназначен для публичного распространения.** v0.1 и база сохранены.')
    replace_section('docs/CHANGES.md','## DRI v0.2 — контекстные рамки\n\n'
        'Созданы config/dri_v02.json, config/dri_v02_rules.json, dri/contextual.py, dri/contextual_index.py, dri/contextual_outputs.py, scripts/calculate_dri_v02.py, tests/test_contextual.py. '
        'Расчётные артефакты: data/dri_v02_units.jsonl, data/dri_v02_monthly.csv, data/dri_v02_comparison.csv, data/dri_v02_manifest.json, docs/DRI_v02.png; '
        'единственный внутренний файл новой экспертной выборки: data/dri_v02_review.json. '
        'Обновлены существующие .gitignore (внутренний файл разметки), README.md, docs/QUALITY_REPORT.md, docs/CHANGES.md и docs/TEST_RESULTS.txt. '
        'База, исходники, DRI v0.1, старые аудиты, зависимости и схема неизменны. Нового сбора, LLM, исторической валидации и публичных текстовых отчётов нет.')
