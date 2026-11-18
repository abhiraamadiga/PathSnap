"""Report actual classifier/HMM development results without claiming final accuracy."""
import argparse
import csv
import json
from pathlib import Path


def write_report(root,output):
    root=Path(root);summary=json.loads((root/'summary.json').read_text());selection=json.loads((root/'selection.json').read_text())
    rows=list(csv.DictReader((root/'comparison.csv').open()))
    lines=['# Step 8: measured HMM/Viterbi results','',
           f"Transition beta selected: **{selection['selected_beta_m']:g} metres**, using the declared five selection trips and mean-trip weak-reference Top-1. Review-trip scores were computed after selection and did not choose beta. Both subsets were used in earlier classifier work, so neither is an independent final model test.",'',
           '| Subset / method | Pooled weak Top-1 | Mean-trip weak Top-1 | Direct continuity | Mean route edit similarity | Mean arc-set F1 | Route parts |',
           '| --- | ---: | ---: | ---: | ---: | ---: | ---: |']
    for subset,methods in summary.items():
        for method,r in methods.items():
            lines.append(f"| {subset} / {method} | {r['weak_reference_top1']:.6f} | {r['mean_trip_weak_reference_top1']:.6f} | {r['direct_continuity']:.6f} | {r['mean_reference_sequence_edit_similarity']:.6f} | {r['mean_reference_arc_set_f1']:.6f} | {r['total_route_parts']} |")
    lines+=['','## Per-trip comparison','',
            '| Trip | Subset | Classifier weak Top-1 | HMM weak Top-1 | Change | Classifier parts | HMM parts |',
            '| --- | --- | ---: | ---: | ---: | ---: | ---: |']
    failures=[]
    for trip in sorted({r['trip_id'] for r in rows}):
        methods={r['method']:r for r in rows if r['trip_id']==trip};a=methods['classifier_only'];b=methods['hmm_viterbi']
        delta=float(b['weak_reference_top1'])-float(a['weak_reference_top1'])
        lines.append(f"| {trip} | {a['subset']} | {float(a['weak_reference_top1']):.6f} | {float(b['weak_reference_top1']):.6f} | {delta:+.6f} | {a['route_parts']} | {b['route_parts']} |")
        if delta<0:failures.append(trip)
    lines+=['','## Interpretation and failure analysis','',
            'Pointwise weak-reference agreement, direct continuity and supplied-reference sequence diagnostics improve in aggregate. Shortest-path expansion is applied to both classifier and HMM states using the same graph/limits. Route parts remain separate at gaps or invalid transitions; no artificial straight connectors are inserted.','',
            f"Trips with lower weak Top-1 after decoding: {', '.join(failures) if failures else 'none in this run'}. Inspect their committed maps and prediction CSVs; the figures do not justify claiming uniform improvement. Sequential smoothing can prefer a connected route over individual weak geometric labels. The present experiment does not establish whether each disagreement is a decoder error, weak-label error or graph/reference limitation.",'',
            f"The HMM has {summary['all']['hmm_viterbi']['decoder_unreachable_resets']} explicit no-valid-transition resets. Gaps and missing candidates also create boundaries. These boundaries are reported rather than hidden by claiming a single connected trajectory.",'',
            'Top-1 is conditional on accepted weak geometric labels (12,262 observations in this dataset), with absent positive candidates counted as incorrect. It is not verified physical ground-truth accuracy. Sequence edit similarity compares the expanded chronological arc list with the supplied route; arc-set F1 ignores order. These use imperfect supplied references and are diagnostic, not proof of correct movement.','',
            '## Runtime evidence','',
            f"Summed classifier predict_proba time across ten trips: {sum(float(r['classifier_seconds']) for r in rows if r['method']=='classifier_only'):.3f} seconds. Transition preparation including bounded shortest-path queries: {sum(float(r['transition_preparation_seconds']) for r in rows if r['method']=='classifier_only'):.3f} seconds. Selected Viterbi passes: {sum(float(r['viterbi_seconds']) for r in rows if r['method']=='hmm_viterbi'):.3f} seconds.",'',
            'These timings exclude file loading, graph construction, route expansion, reference-sequence metrics and map generation; they are not API latency. Transition preparation is reused across beta candidates.','',
            'Maps are in results/maps/hmm_viterbi/. Blue: GPS, green: supplied reference, orange: classifier reconstruction, purple: HMM reconstruction. Internet is required for Folium assets and tiles.','',
            'No evaluator data was read or scored. Next: export the model/preprocessing/decoder inference assets, then implement and test the two-laptop API/UI.','']
    output=Path(output);output.parent.mkdir(parents=True,exist_ok=True);output.write_text('\n'.join(lines))
    plot(rows,root/'comparison.png')


def plot(rows,path):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    trips=sorted({r['trip_id'] for r in rows})
    fig,axes=plt.subplots(1,2,figsize=(13,4.5),layout='constrained')
    for ax,key,title in zip(axes,['weak_reference_top1','reference_sequence_edit_similarity'],['Pointwise weak-reference agreement','Expanded route edit similarity']):
        for method,offset,color in [('classifier_only',-.2,'#e07b1a'),('hmm_viterbi',.2,'#7b2cbf')]:
            values=[float(next(r[key] for r in rows if r['trip_id']==trip and r['method']==method)) for trip in trips]
            ax.bar([i+offset for i in range(len(trips))],values,width=.4,label=method,color=color)
        ax.set_xticks(range(len(trips)),[t[-2:] for t in trips]);ax.set_ylim(0,1);ax.set(title=title,xlabel='Student trip ID suffix');ax.legend(fontsize=8)
    fig.suptitle('Development comparison: first five select beta; last five review it')
    fig.savefig(path,dpi=160);plt.close(fig)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--results',type=Path,default=Path('results/experiments/hmm_viterbi'))
    parser.add_argument('--output',type=Path,default=Path('docs/hmm-results.md'))
    args=parser.parse_args();write_report(args.results,args.output)


if __name__=='__main__':main()
