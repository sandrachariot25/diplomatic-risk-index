// One blind annotation workbook, using the bundled artifact-tool runtime only.
import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath,pathToFileURL} from 'node:url';
import {createRequire} from 'node:module';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
// Windows may refuse a dependency junction in OneDrive. Resolve the public package
// entry from the already-loaded bundled Node runtime without modifying that runtime.
const require=createRequire(pathToFileURL(path.join(path.dirname(path.dirname(process.execPath)),'package.json')));
const {Workbook,SpreadsheetFile}=await import(pathToFileURL(require.resolve('@oai/artifact-tool')).href);
const payload=JSON.parse(await fs.readFile(path.join(root,'.venv','dri_expert_workbook_payload.json'),'utf8'));
const wb=Workbook.create();
const main=wb.worksheets.add('Разметка');
const guide=wb.worksheets.add('Инструкция');
const text=wb.worksheets.add('Тексты');
const colors={ink:'#202833',header:'#303B4A',input:'#FFF2CC',pale:'#F4F6F8',rule:'#D9DEE5'};
const literal=value=>typeof value==='string'&&value.startsWith('=')?"'"+value:value;
function base(sheet,range){
  sheet.showGridLines=false;
  sheet.getRange(range).format.font={name:'Arial',size:11,color:colors.ink};
  sheet.getRange(range).format.verticalAlignment='top';
  sheet.getRange(range).format.wrapText=true;
}
function header(sheet,range){
  sheet.getRange(range).format={fill:colors.header,font:{name:'Arial',size:11,bold:true,color:'#FFFFFF'},
    wrapText:true,horizontalAlignment:'center',verticalAlignment:'center',rowHeight:42};
}
const n=payload.rows.length+1;
base(main,`A1:R${n}`);
const rows=payload.rows.map(row=>row.map((value,i)=>i===1?new Date(value+'T00:00:00Z'):literal(value)));
main.getRange(`A1:R${n}`).values=[payload.headers,...rows];
const table=main.tables.add(`A1:R${n}`,true,'ExpertAnnotations');
table.showFilterButton=true;
header(main,'A1:R1');
const widths={A:10,B:12,C:24,D:18,E:8,F:90,G:24,H:18,I:24,J:29,K:19,L:44,M:42,N:48,O:42,P:29,Q:15,R:22};
for(const [col,width] of Object.entries(widths))main.getRange(`${col}1:${col}${n}`).format.columnWidth=width;
main.getRange(`B2:B${n}`).setNumberFormat('yyyy-mm-dd');
main.getRange(`A2:A${n}`).setNumberFormat('0');
main.getRange(`H2:H${n}`).setNumberFormat('0');
main.getRange(`G2:L${n}`).format.fill=colors.input;
main.getRange(`P2:R${n}`).format.fill=colors.input;
main.getRange(`M2:O${n}`).format.fill=colors.pale;
for(let i=0;i<payload.rows.length;i++){
  const row=payload.rows[i],cjk=row[4]!=='en';
  const lines=Math.ceil(row[5].length/(cjk?40:86))+(row[5].match(/\n/g)||[]).length;
  main.getRange(`A${i+2}:R${i+2}`).format.rowHeight=Math.max(68,Math.min(370,lines*13+22));
}
main.freezePanes.freezeRows(1);main.freezePanes.freezeColumns(1);
const fields={G:'direction',I:'target',J:'ownership',K:'confidence',P:'relevance',Q:'optional_flags',R:'optional_flags'};
for(const [col,key] of Object.entries(fields))main.getRange(`${col}2:${col}${n}`).dataValidation={rule:{type:'list',values:payload.guideline[key]}};
main.dataValidations.add({range:`H2:H${n}`,rule:{type:'whole',operator:'between',formula1:0,formula2:3}});

base(guide,'A1:B24');
guide.getRange('A1').values=[['DRI: инструкция']];
guide.getRange('A1').format.font={name:'Arial',size:16,bold:true};
guide.getRange('A1:B1').format.rowHeight=30;
guide.getRange('A3:B4').values=[['Версия инструкции',payload.guideline.version],['Набор',payload.sample_id]];
guide.getRange('A6:B6').values=[['Правило','Как оценивать']];
guide.getRange(`A7:B${6+payload.guideline.instructions.length}`).values=payload.guideline.instructions;
guide.getRange('A1:A24').format.columnWidth=29;
guide.getRange('B1:B24').format.columnWidth=120;
guide.getRange('A2').format.rowHeight=10;
guide.getRange('A5').format.rowHeight=10;
header(guide,'A6:B6');
guide.getRange('A6:B6').format.rowHeight=26;
for(let i=0;i<payload.guideline.instructions.length;i++){
  const description=payload.guideline.instructions[i][1];
  guide.getRange(`A${i+7}:B${i+7}`).format.rowHeight=Math.max(48,Math.ceil(description.length/100)*15+14);
}
guide.getRange('A3:A4').format.font={name:'Arial',size:11,bold:true};

const tailCount=payload.continuations.length+1;
base(text,`A1:C${tailCount}`);
text.getRange(`A1:C${tailCount}`).values=[['ID','Часть','Оригинальный текст: продолжение'],...payload.continuations.map(row=>row.map(literal))];
header(text,'A1:C1');
text.getRange(`A1:A${tailCount}`).format.columnWidth=12;
text.getRange(`B1:B${tailCount}`).format.columnWidth=10;
text.getRange(`C1:C${tailCount}`).format.columnWidth=105;
text.getRange(`A2:B${tailCount}`).setNumberFormat('0');
for(let i=0;i<payload.continuations.length;i++){
  const s=payload.continuations[i][2];
  text.getRange(`A${i+2}:C${i+2}`).format.rowHeight=Math.max(65,Math.min(340,Math.ceil(s.length/48)*13+20));
}
text.freezePanes.freezeRows(1);
text.tables.add(`A1:C${tailCount}`,true,'SourceContinuations').showFilterButton=true;
wb.recalculate();
const check=await wb.inspect({kind:'table',range:'Разметка!G1:L3',include:'values,formulas',tableMaxRows:3,tableMaxCols:6,maxChars:1800});
console.log(check.ndjson);
const errors=await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!',options:{useRegex:true,maxResults:10},maxChars:500});
console.log(errors.ndjson);
// Internal previews stay in the already-existing ignored environment directory.
for(const [sheetName,range,suffix] of [['Разметка','A1:L3','main'],['Инструкция','A1:B12','guide'],['Тексты','A1:C3','texts']]){
  const blob=await wb.render({sheetName,range,scale:1,format:'png'});
  await fs.writeFile(path.join(root,'.venv',`expert_review_${suffix}.png`),new Uint8Array(await blob.arrayBuffer()));
}
const output=await SpreadsheetFile.exportXlsx(wb);
await output.save(path.join(root,'data','dri_expert_review.xlsx'));
const inspectPath=path.join(root,'data','dri_expert_review.xlsx.inspect.ndjson');
try{await fs.rename(inspectPath,path.join(root,'.venv','dri_expert_review.inspect.ndjson'));}catch(error){if(error.code!=='ENOENT')throw error;}
console.log(JSON.stringify({rows:payload.rows.length,continuations:payload.continuations.length,sheets:3,output:'data/dri_expert_review.xlsx'}));
