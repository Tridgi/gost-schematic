/** Strict JSON text gate for user-controlled ProjectV2 imports.
 * JSON.parse alone silently overwrites duplicate object members. Detect every
 * duplicate decoded property name before accepting the canonical typed model.
 */
export function parseProjectJsonStrict(source:string):unknown {
  if(typeof source!=='string'||source.length>8*1024*1024)
    throw Error('INVALID_JSON_SIZE');
  let index=0;
  const whitespace=()=>{while(index<source.length&&/\s/.test(source[index]))index++;};
  function quoted():string {
    const start=index;
    if(source[index++]!=='"')throw Error('INVALID_JSON_STRING');
    while(index<source.length){
      const char=source[index++];
      if(char==='\\'){
        if(index>=source.length)throw Error('INVALID_JSON_ESCAPE');
        index++;
      }else if(char==='"'){
        try{return JSON.parse(source.slice(start,index)) as string;}
        catch{throw Error('INVALID_JSON_STRING');}
      }
    }
    throw Error('UNTERMINATED_JSON_STRING');
  }
  function value(depth:number):void{
    if(depth>96)throw Error('JSON_TOO_DEEP');
    whitespace();
    if(source[index]==='{'){
      index++;whitespace();
      const keys=new Set<string>();
      if(source[index]==='}') {index++;return;}
      while(index<source.length){
        whitespace();
        const key=quoted();
        if(keys.has(key))throw Error('DUPLICATE_JSON_KEY:'+key);
        keys.add(key);whitespace();
        if(source[index++]!==':')throw Error('INVALID_JSON_COLON');
        value(depth+1);whitespace();
        if(source[index]==='}') {index++;return;}
        if(source[index++]!==',')throw Error('INVALID_JSON_COMMA');
      }
      throw Error('INVALID_JSON_OBJECT');
    }
    if(source[index]==='['){
      index++;whitespace();
      if(source[index]===']'){index++;return;}
      while(index<source.length){
        value(depth+1);whitespace();
        if(source[index]===']'){index++;return;}
        if(source[index++]!==',')throw Error('INVALID_JSON_ARRAY');
      }
      throw Error('INVALID_JSON_ARRAY');
    }
    if(source[index]==='"'){quoted();return;}
    const start=index;
    while(index<source.length&&!/[\s,\]}]/.test(source[index]))index++;
    if(index===start)throw Error('INVALID_JSON_VALUE');
    try{JSON.parse(source.slice(start,index));}
    catch{throw Error('INVALID_JSON_VALUE');}
  }
  value(0);whitespace();
  if(index!==source.length)throw Error('JSON_TRAILING_CONTENT');
  return JSON.parse(source) as unknown;
}
