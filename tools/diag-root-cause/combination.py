#!/usr/bin/env python3
import argparse
import os
import sys
from datetime import datetime

from jinja2 import Template

import diag

CUR_DIR = os.fspath(os.path.dirname(__file__))
ALPHAS = [0.01, 0.02, 0.03, 0.04, 0.05]

MARKDOWN_TMPL = """# Generated Causality Graphs at {{ ts }}

{% for chaos_type, chaos_comp in items.items() -%}
{% for comp_name, item in chaos_comp.items() -%}

## {{ chaos_type }} in {{ comp_name }}

{% for val in item.results %}

### params: stable {{ val.pc_stable }}, alpha {{ val.alpha }}

- chaos type: {{ chaos_type }}
- chaos component: {{ comp_name }}
- grafana dashboard url: <{{ val.meta.metrics_meta.grafana_dashboard_url }}>
- causal graph nodes: {{ val.meta.causal_graph_stats.nodes_num }}
- causal graph edges: {{ val.meta.causal_graph_stats.edges_num }}
- found cause metrics: 
{%- for metric in val.meta.causal_graph_stats.cause_metric_nodes -%}
{{ metric }},
{%- endfor %}
{% set total = val.meta.metrics_dimension.total -%}
- tsdr metrics total: {{ total[0]|string + '/' + total[1]|string + '/' + total[2]|string }}

![](data:image/png;base64,{{ val.meta.raw_image }})

{% endfor %}
{%- endfor %}
{%- endfor %}
"""


def log(msg):
    print(msg, file=sys.stderr)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("tsdr_files",
                        nargs='+',
                        help="out directory")
    parser.add_argument("--out-dir", required=True, help="out directory")
    parser.add_argument("--out-markdown", help="out markdown file")
    args = parser.parse_args()

    ts = datetime.now().strftime("%Y%m%d%H%M%S")
    dir = os.path.join(args.out_dir, ts)
    os.makedirs(dir)

    template = Template(MARKDOWN_TMPL)
    items = {}
    for tsdr_file in args.tsdr_files:
        for pc_stable in [True]:
            for alpha in ALPHAS:
                try:
                    meta = diag.diag(tsdr_file, alpha, pc_stable, dir)
                    chaosType = meta['metrics_meta']['injected_chaos_type']
                    chaosComp = meta['metrics_meta']['chaos_injected_component']
                    items.setdefault(chaosType, {})
                    items[chaosType].setdefault(chaosComp, {
                        'results': [],
                    })
                    items[chaosType][chaosComp]['results'].append({
                        'meta': meta,
                        'pc_stable': 1 if pc_stable else 0,
                        'alpha': alpha,
                    })
                except ValueError as e:
                    log(e)

    if args.out_markdown is not None:
        dst = template.render(items=items, ts=ts)
        with open(args.out_markdown, mode='w') as f:
            f.write(str(dst))


if __name__ == '__main__':
    main()
