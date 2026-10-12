"""Workshop 1 - Tareas 2 y 4. Python estándar, sin dependencias externas."""
import csv, hashlib, json, math, random, statistics, time
from pathlib import Path
from collections import Counter
BASE=Path(__file__).resolve().parent
OUT=BASE/'resultados'; OUT.mkdir(exist_ok=True)

def quicksort(values, randomized=False, seed=42):
    """Quicksort in-place iterativo; pivote final fijo o aleatorio."""
    a=list(values); rng=random.Random(seed); stack=[(0,len(a)-1)]
    while stack:
        lo,hi=stack.pop()
        while lo<hi:
            if randomized:
                j=rng.randint(lo,hi);a[j],a[hi]=a[hi],a[j]
            pivot=a[hi];i=lo
            for j in range(lo,hi):
                if a[j]<=pivot:
                    a[i],a[j]=a[j],a[i];i+=1
            a[i],a[hi]=a[hi],a[i]
            # Process smaller partition first to limit stack depth
            if i-lo < hi-i:
                if i+1<hi:stack.append((i+1,hi))
                hi=i-1
            else:
                if lo<i-1:stack.append((lo,i-1))
                lo=i+1
    return a

def stable_hash(value):
    return int.from_bytes(hashlib.sha256(str(value).encode('utf-8')).digest()[:8],'big')

def bucket_loads(ids,buckets,method):
    loads=[0]*buckets
    for uid in ids:
        a=stable_hash('A:'+uid)%buckets
        if method=='chaining':chosen=a
        else:
            b=stable_hash('B:'+uid)%buckets
            chosen=a if loads[a]<=loads[b] else b
        loads[chosen]+=1
    return loads

def write_csv(path,rows):
    if not rows:return
    with path.open('w',newline='',encoding='utf-8-sig') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

def main():
    with (BASE/'datos/videos_equipo4.json').open(encoding='utf-8') as f:videos=json.load(f)
    assert isinstance(videos,list) and all('duration_sec' in v and 'uploader_id' in v for v in videos)
    durations=[int(v['duration_sec']) for v in videos]
    ids=[str(v['uploader_id'])+':'+str(v['video_id']) for v in videos]
    print('Registros leídos:',len(videos))
    # Sorting benchmarks: input types expose strengths and weaknesses.
    rows=[]
    for n in (1000,3000,5000,10000):
        base=durations[:n]
        for scenario,vals in [('original',base),('ordenado',sorted(base)),('inverso',sorted(base,reverse=True))]:
            for alg,randomized in [('determinista',False),('aleatorizado',True)]:
                times=[]
                for trial in range(3):
                    t=time.perf_counter();actual=quicksort(vals,randomized,seed=42+trial)
                    elapsed=(time.perf_counter()-t)*1000
                    assert actual==sorted(vals),f'Fallo de ordenamiento: {scenario}, {alg}'
                    times.append(elapsed)
                rows.append({'n':n,'escenario':scenario,'algoritmo':alg,'tiempo_promedio_ms':round(statistics.mean(times),3),'tiempo_min_ms':round(min(times),3),'repeticiones':len(times)})
    write_csv(OUT/'quicksort_comparacion.csv',rows)
    # Compare same bucket count and identical items, two choices is load-aware.
    hashing=[]
    for n in (1000,5000,10000):
        for buckets in (128,512,1024):
            for method in ('chaining','two_choices'):
                loads=bucket_loads(ids[:n],buckets,method)
                hashing.append({'n':n,'buckets':buckets,'metodo':method,'carga_maxima':max(loads),'carga_media':round(statistics.mean(loads),4),'desviacion_estandar':round(statistics.pstdev(loads),4),'buckets_vacios':loads.count(0),'colisiones_insercion':sum(max(0,x-1) for x in loads)})
    write_csv(OUT/'hashing_comparacion.csv',hashing)
    with (OUT/'resumen.json').open('w',encoding='utf-8') as f:
        json.dump({'registros':len(videos),'campos':list(videos[0]),'nota':'Resultados empíricos del equipo; tiempos dependen del computador y la carga del sistema.'},f,indent=2,ensure_ascii=False)
    print('Pruebas completadas. Resultados en:',OUT)
    print('Ejemplo QuickSort:',rows[0]);print('Ejemplo hashing:',hashing[0])
if __name__=='__main__':main()
