"""Small stdio MCP client. Captures raw responses; does not score recovery."""
import json
import queue
import subprocess
import sys
import threading
import time
from prepare import ROOT, command, environment

class Client:
    def __init__(self,tool,label):
        self.tool,self.label,self.sequence=tool,label,0
        self.responses=queue.Queue()
        self.stderr=open(ROOT/'logs'/f'{label}-stderr.txt','w',encoding='utf-8')
        self.proc=subprocess.Popen(command(tool)+['mcp'],cwd=ROOT,env=environment(tool),stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=self.stderr,text=True,encoding='utf-8',errors='replace',bufsize=1)
        self.log=open(ROOT/'logs'/f'{label}-rpc.jsonl','w',encoding='utf-8')
        threading.Thread(target=self._read,daemon=True).start()
    def _read(self):
        for line in self.proc.stdout:
            try:self.responses.put(json.loads(line))
            except json.JSONDecodeError:self.responses.put({'unparsed_stdout':line})
    def call(self,method,params=None,timeout=90):
        self.sequence+=1
        msg={'jsonrpc':'2.0','id':self.sequence,'method':method}
        if params is not None:msg['params']=params
        start=time.perf_counter()
        self.proc.stdin.write(json.dumps(msg)+'\n');self.proc.stdin.flush()
        while time.perf_counter()-start<timeout:
            try:response=self.responses.get(timeout=1)
            except queue.Empty:
                if self.proc.poll() is not None:raise RuntimeError(f'{self.tool} exited {self.proc.returncode}')
                continue
            if response.get('id')!=self.sequence:
                self.log.write(json.dumps({'event':response})+'\n');self.log.flush();continue
            record={'request':msg,'response':response,'elapsed_seconds':round(time.perf_counter()-start,4)}
            self.log.write(json.dumps(record)+'\n');self.log.flush()
            return response
        raise TimeoutError(f'{self.tool} {method}')
    def initialize(self):
        result=self.call('initialize',{'protocolVersion':'2025-11-25','capabilities':{},'clientInfo':{'name':'scoped-discovery-probe','version':'0.1'}})
        self.proc.stdin.write(json.dumps({'jsonrpc':'2.0','method':'notifications/initialized'})+'\n');self.proc.stdin.flush()
        return result
    def close(self):
        # Do not flush a pipe whose reader may be stuck during startup.
        self.proc.terminate()
        try:self.proc.wait(timeout=12)
        except subprocess.TimeoutExpired:self.proc.terminate();self.proc.wait(timeout=8)
        self.log.close();self.stderr.close()

if __name__=='__main__':
    import faulthandler
    faulthandler.dump_traceback_later(20,repeat=True)
    tool=sys.argv[1]
    client=Client(tool,f'{tool}-schema')
    try:
        init=client.initialize()
        result=client.call('tools/list')
        (ROOT/f'{tool}-tools.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
        print(json.dumps({'tool':tool,'init_error':init.get('error'),'tools':[t['name'] for t in result.get('result',{}).get('tools',[])]}),flush=True)
    finally:client.close()
