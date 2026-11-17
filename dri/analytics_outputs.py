"""One set of aggregate artifacts. No source text or reconstructable token dump."""
import csv
import hashlib
import importlib.metadata
import io
import json
import os
import platform
import re
import sys
from collections import defaultdict,Counter
from pathlib import Path
from .paths import ROOT,write_generated
from .analytical_sample import digest

def dump(value):return json.dumps(value,ensure_ascii=False,sort_keys=True,allow_nan=False)

def file_sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()

def runtime_manifest():
    packages={line.split('==')[0]:line.split('==')[1] for line in (ROOT/'requirements-analytics.lock').read_text().splitlines() if '==' in line}
    actual={name:importlib.metadata.version(name) for name in packages}
    if actual!=packages:raise RuntimeError('Analysis dependency versions differ from requirements-analytics.lock')
    hashes={}
    for name in ('Janome','kiwipiepy_model'):
        d=importlib.metadata.distribution(name);files={}
        for p in d.files:
            if (str(p).startswith('janome/sysdic/') or str(p).startswith('kiwipiepy_model/')) and not str(p).endswith('.pyc'):
                files[str(p)]=file_sha(d.locate_file(p))
        hashes[name]={'files':len(files),'dictionary_files_sha256':digest(files)}
    return {'python':sys.version,'platform':platform.platform(),'packages':actual,'dictionaries':hashes}

def label(row):
    forms={'complete_speech':'full speech','complete_official_statement':'full statement',
           'selected_turns_partial_floor':'selected turns','sentence_excerpt':'sentence excerpt',
           'legacy_excerpt':'legacy excerpt','short_quote_fragment':'short quote',
           'legacy_quote_unknown_completeness':'legacy quote (?)'}
    source={'mofa_kr':'MOFA KR','kokkai_jp':'NDL Kokkai','assembly_kr':'KR Assembly','korea_government_kr':'KR Government'}.get(row['source_id'],row['source_id'])
    return source+' / '+forms.get(row['text_form'],row['text_form'])+(' / translation' if row['version']=='unofficial_translation' else '')

def plots(result):
    cache=ROOT/'.venv/matplotlib-cache';cache.mkdir(parents=True,exist_ok=True)
    os.environ['MPLCONFIGDIR']=str(cache)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import numpy as np
    from matplotlib.colors import ListedColormap
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':9,'axes.grid':True,'grid.alpha':0.18})
    rows=result['monthly'];groups=defaultdict(list)
    for row in rows:groups[row['component_id']].append(row)
    panels=[('ROK','en'),('JPN','ja'),('ROK','ko')]
    fig,axes=plt.subplots(3,1,figsize=(14,11),sharex=True)
    for ax,(country,lang) in zip(axes,panels):
        for key,rs in groups.items():
            if (rs[0]['country'],rs[0]['language'])!=(country,lang):continue
            x=np.arange(len(rs));y=np.array([r['raw_rate_per_1000'] if r['raw_rate_per_1000'] is not None else np.nan for r in rs])
            line,=ax.plot(x,y,lw=1,alpha=.65,label=label(rs[0]))
            supported=[i for i,r in enumerate(rs) if r['status']=='supported']
            low=[i for i,r in enumerate(rs) if r['status']=='insufficient_volume']
            if low:ax.scatter(x[low],y[low],s=28,facecolors='none',edgecolors=line.get_color(),zorder=3)
            if supported:ax.scatter(x[supported],y[supported],s=25,color=line.get_color(),zorder=4)
        ax.set_title(country+' / '+lang+' — отдельные компоненты; '+('полных японских речей нет' if lang=='ja' else 'разные формы текста разделены'),loc='left')
        ax.set_ylabel('Выражений / 1 000 токенов')
        observed=[r['raw_rate_per_1000'] for rs in groups.values() if (rs[0]['country'],rs[0]['language'])==(country,lang)
                  for r in rs if r['raw_rate_per_1000'] is not None]
        ymax=max(observed,default=0)
        ax.set_ylim(-.02*max(1,ymax),max(1,ymax*1.12))
        if ymax==0:
            ax.set_yticks([0,.25,.5,.75,1])
            ax.text(.02,.65,'Учтённых выражений нет. Это не отсутствие напряжённости:\nполнота словаря и контекстных правил не установлена.',transform=ax.transAxes,color='#555555')
        ax.legend(fontsize=8,loc='upper right')
    months=[r['month'] for r in next(iter(groups.values()))]
    ticks=[i for i,m in enumerate(months) if m.endswith('-01')]
    ticklabels=[months[i][:4] for i in ticks]
    axes[-1].set_xticks(ticks,ticklabels);axes[-1].set_xlim(-1,len(months))
    fig.suptitle('DRI v0.1 — месячная частота словарных выражений\nЕдиный индекс не агрегирован; языки и полнота текстов несопоставимы',fontsize=14)
    fig.text(.5,.015,'Полые точки: объём ниже порога. Пропуски не заменены нулями. Ноль — отсутствие учтённых выражений, а не отсутствие напряжённости.',ha='center',fontsize=9)
    fig.tight_layout(rect=(0,.04,1,.93));fig.savefig(ROOT/'docs/DRI_v01.png',dpi=150);plt.close(fig)

    units=[u for u in result['units'] if not u['exclusion_reason']]
    fig,axs=plt.subplots(2,2,figsize=(16,10))
    colors=plt.get_cmap('tab10')
    for j,(key,rs) in enumerate(groups.items()):
        axs[0,0].plot(range(len(rs)),[r['token_count'] if r['unit_count'] else np.nan for r in rs],label=label(rs[0]),color=colors(j%10),lw=1)
    axs[0,0].set_yscale('log');axs[0,0].set_title('Объём текста по компонентам; логарифмическая ось')
    axs[0,0].set_ylabel('Токены соответствующего анализатора');axs[0,0].set_xticks(ticks,ticklabels);axs[0,0].legend(fontsize=6)
    values=[];names=[]
    for key,rs in groups.items():
        us=[u['token_count'] for u in units if '|'.join(u[k] for k in ('country','language','source_type','source_id','text_form','version'))==key]
        values.append(us);names.append(rs[0]['country']+'/'+rs[0]['language']+' '+label(rs[0]))
    axs[0,1].boxplot(values,vert=False,tick_labels=names,showfliers=False)
    axs[0,1].set_xscale('log');axs[0,1].tick_params(axis='y',labelsize=7)
    axs[0,1].set_title('Длина уникальных единиц; разные языки не объединены')
    matrix=np.array([[{'no_data':0,'insufficient_volume':1,'supported':2}[r['status']] for r in rs] for rs in groups.values()])
    im=axs[1,0].imshow(matrix,aspect='auto',interpolation='nearest',cmap=ListedColormap(['#dddddd','#f4bf62','#267e6d']),vmin=0,vmax=2)
    axs[1,0].set_yticks(range(len(groups)),[rs[0]['country']+'/'+rs[0]['language']+' '+label(rs[0]) for rs in groups.values()],fontsize=7)
    axs[1,0].set_xticks(ticks,ticklabels);axs[1,0].grid(False)
    axs[1,0].set_title('Покрытие: серый — нет текста; жёлтый — мало; зелёный — порог объёма пройден')
    roles=Counter((u['country'],u['component_role']) for u in units)
    labels=['ROK полные','ROK фрагменты','JPN полные','JPN фрагменты']
    vals=[roles[('ROK','main')],roles[('ROK','diagnostic_partial_text')],roles[('JPN','main')],roles[('JPN','diagnostic_partial_text')]]
    axs[1,1].bar(labels,vals,color=['#267e6d','#f4bf62','#267e6d','#f4bf62'])
    for i,v in enumerate(vals):axs[1,1].text(i,v+10,str(v),ha='center')
    axs[1,1].set_ylim(0,max(vals)*1.18);axs[1,1].set_title('Чувствительность: исключение японских фрагментов\nоставляет японскую сторону без расчётных единиц')
    axs[1,1].set_ylabel('Уникальные единицы');fig.suptitle('DRI v0.1 — диагностика состава и доступности данных',fontsize=15)
    fig.tight_layout(rect=(0,.02,1,.95));fig.savefig(ROOT/'docs/DRI_v01_diagnostics.png',dpi=150);plt.close(fig)

def write_outputs(result,config,lexicon,reproduced):
    runtime=runtime_manifest()
    stream=io.StringIO(newline='');writer=csv.DictWriter(stream,fieldnames=list(result['monthly'][0]))
    writer.writeheader();writer.writerows(result['monthly'])
    write_generated(ROOT/'data/dri_v01_monthly.csv',stream.getvalue())
    for name,key in [('units','units'),('matches','matches')]:
        write_generated(ROOT/f'data/dri_v01_{name}.jsonl',''.join(dump(r)+'\n' for r in result[key]))
    plots(result)
    code=['dri/tokenization.py','dri/rhetoric.py','dri/analytical_sample.py','dri/analytics.py','dri/analytics_outputs.py',
          'dri/identity.py','dri/connectors/assembly_pdf.py','dri/connectors/korea.py','dri/html.py','scripts/calculate_dri.py']
    review=ROOT/'config/dri_v01_review.json'
    manifest={'model':'DRI v0.1','config':config,'lexicon_sha256':digest(lexicon),'lexicon_entries':len(lexicon['entries']),
        'code_sha256':{p:file_sha(ROOT/p) for p in code},'runtime':runtime,
        'result_sha256':digest(result),'same_snapshot_recalculation_identical':reproduced,
        'summary':result['summary'],'manual_review_sha256':file_sha(review) if review.exists() else None,
        'outputs_sha256':{p:file_sha(ROOT/p) for p in ['data/dri_v01_monthly.csv','data/dri_v01_units.jsonl','data/dri_v01_matches.jsonl','docs/DRI_v01.png','docs/DRI_v01_diagnostics.png']}}
    write_generated(ROOT/'data/dri_v01_manifest.json',json.dumps(manifest,ensure_ascii=False,indent=2,sort_keys=True)+'\n')
    update_docs(result,config,manifest)

def update_docs(result,config,manifest):
    marker='<!-- DRI_V01_START -->';end='<!-- DRI_V01_END -->'
    def section(path,text):
        p=ROOT/path;old=p.read_text(encoding='utf-8')
        old=re.sub(re.escape(marker)+'.*?'+re.escape(end),'',old,flags=re.S).rstrip()
        write_generated(p,old+'\n\n'+marker+'\n'+text+'\n'+end+'\n')
    s=result['summary'];review_path=ROOT/'config/dri_v01_review.json'
    review=json.loads(review_path.read_text(encoding='utf-8')) if review_path.exists() else {'records':[]}
    match_ids={m['match_id']:m for m in result['matches']}
    valid_review=[r for r in review['records'] if r['match_id'] in match_ids and r['input_text_sha256']==match_ids[r['match_id']]['input_text_sha256']
                  and r['rule_decision_at_review']==match_ids[r['match_id']]['decision']]
    lines=['## DRI v0.1 — экспериментальная частота конфликтных выражений',
        '', 'Это описательная лексическая метрика, не вероятность войны, не прогноз и не проверенный классификатор политических намерений. Единого значения DRI и шкалы 0–100 нет: отсутствует сопоставимое двустороннее покрытие.',
        '',f'Из {s["statement_records"]} заявлений в компоненты вошло {s["included_statement_records"]}; исключено {s["excluded_statement_records"]}: `{s["excluded_reasons"]}`. Полных речей/самостоятельных официальных заявлений: **{s["main_complete_units"]}**; фрагментарных диагностических единиц: **{s["diagnostic_partial_units"]}**. Каждая единица — уникальное событие/автор/дата; повторные источники не увеличивают число сигналов.',
        '',f'Документы без самостоятельной привязки к заявлению: {s["document_only_records_not_signals"]}; библиография без текста: {s["bibliographic_documents_without_text"]}. GDELT отдельно: `{s["gdelt_separate"]}`. Ни пересказы встреч, ни GDELT автоматически в речевые сигналы не преобразованы. Все 1050 исходных записей остаются в базе; аналитика открывает SQLite в режиме read-only.',
        '', '### Формула и единица подсчёта',
        '', '`F[g,t] = 1000 × sum(counted_expressions[u]) / sum(analyzer_tokens[u])`, где t — календарный месяц, g — страна × опубликованный язык × primary/secondary × конкретный источник × полнота текста × статус оригинала/перевода. Это отношение сумм, не среднее частот коротких и длинных текстов. Числовых весов должностям и источникам нет.',
        '', 'Полный текст самостоятельной речи заменяет вложенную цитату, а не складывается с ней. Протокол не берётся целиком за одну речь. Для парламентских эпизодов используются только проверенные реплики; полнота подтверждается покрытием всех реплик автора в его эпизоде. В 2015 году это шесть полных выступлений, в 2019 — десять частичных эпизодов. Цитатные интервалы одного источника объединяются при доказанном перекрытии; разные реплики и разные даты не склеиваются.',
        '', 'Прежние possible_duplicate не переаудировались и не являются основанием склеивать похожие речи разных дат. Неопределённость сохранена в поле possible_duplicate_candidates каждой аналитической единицы; автоматическая агрегация опирается только на явную идентичность события, автора и даты.',
        '', 'Длина документа не доказывает полноту. Для двух старых комментариев МИД полнота теперь подтверждена точным повторным разбором сохранённого HTML, его SHA-256, датой, заголовком и атрибуцией: config/dri_v01_completeness.json. Полные тела заменили 25-словные цитаты только во внутреннем расчёте; исходные записи и ограничения публикации не изменены, разрешение на распространение не предполагается. Журналистская интерпретация не добавляется к словам политика; для вторичного источника требуется подтверждённая дословная атрибуция, а официальный первичный источник имеет приоритет как доказательство, без политического веса.',
        '', 'Дата речи приоритетна. Для самостоятельного официального письменного заявления допустима его дата публикации с отдельной пометкой, без выдумывания даты устного выступления. Published language подтверждается текстом источника/цитаты; неизвестный исходный язык английской версии не объявляется английским оригиналом.',
        '', 'Английский: Unicode-границы слов, casefold и конечная карта только явных словоформ. Корейский: Kiwi/CoNg, морфемы с частицами и окончаниями в знаменателе; space_tolerance=1 допускает один типографский разрыв, но не восстанавливает пропущенные символы PDF. Японский: Janome/IPADIC, леммы и морфемы без пунктуации. Поиск использует последовательности содержательных лемм, а не подстроки; английские слова, корейские и японские морфемы не взаимозаменяемы.',
        '', 'Позиции char_start/char_end относятся к подготовленному фрагменту (NFC и нормализованные пробелы), а не к байтам PDF. source_ref указывает исходный документ/цитату или реплику и диапазон в её исходном тексте; fragment_provenance и token_ledger_sha256 позволяют воспроизвести токены через --explain без публикации полного текста.',
        '', f'Словарь `{config["lexicon"]}`: {manifest["lexicon_entries"]} выражений в семи заданных категориях, с языком, правилами и синтетическими примерами ошибок. Выражения не подбирались по датам кризисов; веса не оценивались. Перекрывающиеся варианты дают одно, самое длинное, совпадение.',
        '', 'Контекстные правила воздерживаются от подсчёта при цитировании, сообщении чужой позиции, отрицании рядом, гипотезе/вопросе, конкурирующем третьем государстве или отсутствии явной второй стороны в том же предложении. Именные экспортные ограничения требуют явной отрицательной оценки; одно упоминание войны, санкций или КНДР не является признаком угрозы. Отрицание, встроенное в словарное выражение, не отменяет его самого. Это консервативные локальные правила; разрешение местоимений, сложной вложенной речи, иронии и полной области отрицания не реализовано. Ложные отрицания и ложные срабатывания остаются.',
        '', '### Объём и временной фон',
        '',f'Порог объёма месяца: {config["min_month_units"]} единиц и {config["min_month_tokens"]} токенов одного компонента. Это заранее заданный технический фильтр, не доказанная статистическая достаточность. Наблюдаемая сырая частота сохраняется и ниже порога, но dri_component там пуст. Месяц без текстов: frequency/count пусты, а не 0. Наблюдаемый ноль означает лишь отсутствие учтённых словарных выражений.',
        '', 'Прохождение порога не выравнивает точность месяцев с разным объёмом и не делает зависимые выступления независимыми. Доверительные интервалы, распределительная модель редких счётчиков и значимость аномалий не оценивались. Все недостаточные компонент-месяцы перечислены в CSV: фильтр status=insufficient_volume; отсутствие текстов отдельно status=no_data.',
        '', '`robust_deviation = (F - median(past)) / (1.4826 × MAD(past))`. Только предыдущие поддержанные объёмом месяцы за 60 календарных месяцев, минимум 12 наблюдаемых месяцев и 4 ненулевых. При нулевом MAD или недостаточном фоне значение пусто. Будущее и текущий месяц в фон не входят. Порог 3.5 — диагностическая метка, не p-value и не обученный кризисный порог; статистическая применимость должна проверяться отдельно. [NIST: modified Z-score и ограничения его интерпретации](https://www.itl.nist.gov/div898/handbook/eda/section3/eda35h.htm).',
        '',f'Получено {s["component_count"]} раздельных компонентов. Состояния компонент-месяцев: `{s["monthly_states"]}`; поддержанных месяцев основных полных компонентов: {s["supported_main_component_months"]}. Фон: `{s["robust_background_states"]}`. Текущих данных недостаточно для робастных аномалий: в таблице пустые значения, а не искусственные нули.',
        '', '### Выборка по годам',
        '', '| Год | РК полные | РК диагностические | Япония полные | Япония диагностические |',
        '|---|---:|---:|---:|---:|']
    for year in range(2015,2027):
        cs={r['country']:r for r in s['coverage_by_year'] if r['year']==year}
        lines.append(f'| {year} | {cs["ROK"]["main_complete_units"]} | {cs["ROK"]["diagnostic_partial_units"]} | {cs["JPN"]["main_complete_units"]} | {cs["JPN"]["diagnostic_partial_units"]} |')
    lines+=['','### Длина текстов и сопоставимость','','| Страна / язык | Источник / форма | N | Мин. токенов | Медиана | Макс. |','|---|---|---:|---:|---:|---:|']
    for r in s['lengths']:lines.append(f'| {r["country"]} / {r["language"]} | {r["source_id"]} / {r["text_form"]} | {r["units"]} | {r["min_tokens"]} | {r["median_tokens"]} | {r["max_tokens"]} |')
    lines+=['',f'Исключение коротких японских фрагментов удаляет {s["short_japanese_sensitivity"]["removed_units"]} единиц и оставляет {s["short_japanese_sensitivity"]["remaining_japanese_units"]} японских единиц. Эффект на единый DRI неопределён, потому что сам общий показатель не идентифицирован. Усреднять эти ряды с МИД РК запрещено текущей методикой.',
        '', 'Способ обнаружения создаёт систематические смещения: запрос 日韓, прежний фильтр 大臣, выбор одного короткого законченного предложения, старые обрезанные фрагменты и первые 25 слов комментариев МИД. Поэтому частота отражает сохранённую выборку, а не частоту риторики всего государства; тип источника, язык и полнота смешаны с механизмом отбора. Большое число полных отчётов МИД о встречах не решает нехватку самостоятельных выступлений.',
        '', 'Используется современный ретроспективный срез корпуса, а не архив версий, доступных исследователю в каждом историческом месяце. Отсутствие будущих значений в формуле фона не означает, что весь корпус был доступен тогда в реальном времени. Для будущего прогнозного backtest нужны временные срезы доступности и учёт дат поздней публикации/исправлений. Такая проверка здесь не выполнялась.',
        '', '### Небольшой ручной аудит выражений',
        '',f'Проверено агентом {len(valid_review)} совпадений/кандидатов по сохранённым текстам, без повторения прежнего аудита 50 заявлений. Это целевая проверка с отдельными языками и решениями, не случайная независимая валидация. Полные контексты не публикуются. Записи проверки: config/dri_v01_review.json; признаки и позиции: data/dri_v01_matches.jsonl.',
        '', '| Unit | Язык | Решение правила | Ручная оценка | Замечание |','|---:|---|---|---|---|']
    for r in valid_review:
        m=match_ids[r['match_id']];lines.append(f'| {m["unit_id"]} | {m["language"]} | {m["decision"]} / {m["reason"] or "explicit lexical attribution"} | {r["assessment"]} | {r["note"]} |')
    lines+=['', 'Аудит обнаружил как минимум один пропуск собственной явной отрицательной оценки из-за ограниченного списка контекстных маркеров и несколько слишком консервативных отказов в смешанных/анафорических предложениях. Словарь после просмотра этих случаев не подгонялся. В текущем расчёте корейские компоненты имеют словарный ноль, хотя в их текстах присутствует критическая риторика; это подтверждённое ограничение измерения. Обобщённая точность и полнота классификации не установлены.',
        '', 'Автоматические тесты проверяют программные свойства, а не точность политической классификации. Предиктивная/историческая валидация по событиям не проводилась; будущие исходы не использовались.',
        '', '### Артефакты и воспроизведение',
        '', 'data/dri_v01_monthly.csv — месячная таблица с пропусками и диагностикой; data/dri_v01_units.jsonl — включение/исключение каждой записи и источники; data/dri_v01_matches.jsonl — найденные выражения, решения и позиции без исходных текстов; data/dri_v01_manifest.json — хэши, версии, параметры, показатели покрытия. docs/DRI_v01.png — динамика компонентов; docs/DRI_v01_diagnostics.png — объём, длина, покрытие и зависимость от фрагментов.',
        '', 'Повтор: `.venv\\Scripts\\python.exe scripts/calculate_dri.py --verify-reproducibility`. Для внутренней проверки токенов/совпадений одной записи: `.venv\\Scripts\\python.exe scripts/calculate_dri.py --explain ID`. Она выводит текстовые токены в терминал; не использовать вывод как публичную выгрузку. Зависимости: requirements-analytics.lock; словари/модели токенизации хэшированы. База не меняется; новых таблиц, LLM и массового сбора нет.']
    section('docs/QUALITY_REPORT.md','\n'.join(lines))
    section('README.md','## DRI v0.1 — воспроизводимые компоненты\n\n'
        'Аналитическая модель добавлена как офлайн-этап; исходный корпус и схема 4 не изменены. '
        f'Из {s["statement_records"]} записей включено {s["included_statement_records"]}, из них полных {s["main_complete_units"]}; остальные пригодны только для диагностических частот фрагментов. '
        'Единый индекс и шкала 0–100 не агрегированы из несопоставимых языковых/источниковых рядов. Это не вероятность конфликта.\n\n'
        'Среда проверена на Python 3.12.14 / Windows x64. Внутри проекта: `py -3.12 -m venv .venv`; установка после просмотра плана: '
        '`python -m pip --python .venv/Scripts/python.exe install -r requirements-analytics.lock`. '
        'Установка обращается к PyPI; последующий расчёт сети не требует. '\
        'Расчёт: `.venv\\Scripts\\python.exe scripts/calculate_dri.py --verify-reproducibility`; '
        'все тесты: `.venv\\Scripts\\python.exe scripts/run_tests.py`. '
        'Словарь — config/dri_v01_lexicon.json, параметры — config/dri_v01.json. '
        'Формула, диагностика, ограничения и аудит выражений — в существующем docs/QUALITY_REPORT.md. '
        'Результаты: data/dri_v01_monthly.csv, docs/DRI_v01.png и docs/DRI_v01_diagnostics.png. '
        'Полные внутренние тексты в аналитические файлы не включаются.')
    section('docs/SOURCE_AUDIT.md','## Источники в аналитике DRI v0.1\n\n'
        'Новых обращений к корпусным источникам, их повторного аудита и сбора нет. '
        'Существующие ограничения публикации сохраняются: аналитические JSONL содержат идентификаторы, позиции, хэши и счётчики, без исходных текстов или списка слов, восстанавливающего внутренний документ. '
        'GDELT и библиография отделены от речевого расчёта. Ни новостной пересказ, ни полный многоголосый протокол не превращаются в самостоятельное заявление. '
        'Технические зависимости проверены по первичным описаниям: [Kiwi](https://pypi.org/project/kiwipiepy/0.22.2/), '
        '[Janome/IPADIC](https://janome.mocobeta.dev/en/), [Matplotlib](https://pypi.org/project/matplotlib/3.10.7/). '
        'Морфологические модели используются локально для сегментации, а не для прогнозирования или LLM-разметки. Установлены только в .venv проекта, версии и словарные файлы фиксированы в manifest/lock.')
    section('docs/CHANGES.md','## DRI v0.1 — первая аналитическая реализация\n\n'
        'Созданы dri/tokenization.py, dri/rhetoric.py, dri/analytical_sample.py, dri/analytics.py, dri/analytics_outputs.py, '
        'scripts/calculate_dri.py, tests/test_analytics.py, config/dri_v01.json, config/dri_v01_lexicon.json, config/dri_v01_review.json, requirements-analytics.lock. '
        'Обновлены pyproject.toml, .gitignore, README.md, docs/QUALITY_REPORT.md, docs/SOURCE_AUDIT.md, docs/CHANGES.md и docs/TEST_RESULTS.txt. '
        'В dri/connectors/assembly_pdf.py импорт PDF-библиотеки сделан ленивым, чтобы офлайн-аналитика существующих извлечений не требовала PDF-парсинга. '
        'Единственные новые расчётные артефакты: data/dri_v01_monthly.csv, data/dri_v01_units.jsonl, data/dri_v01_matches.jsonl, data/dri_v01_manifest.json, docs/DRI_v01.png, docs/DRI_v01_diagnostics.png. '
        'Локальная .venv содержит зависимости, новая база/таблицы не создавались. База открывается read-only; источники и старые аудиты не изменены. '
        'Реализованы морфология EN/KO/JA, атрибутивные ограничения, отношение сумм, раздельные ряды, пустые месяцы, фон только по прошлому и отказ от шкалы/агрегации при недостатке данных. '
        'Проверены токены, границы слов, отрицание/цитирование, повторные источники, пропуски, отсутствие утечки и детерминизм. '
        'Кризисные даты, исходы и политические веса при разработке не использовались; прогнозная модель и лендинг не создавались.')
