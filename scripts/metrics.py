#!/usr/bin/env python
# coding: utf-8

import scanpy as sc
import scIB
import warnings
warnings.filterwarnings('ignore')

if __name__=='__main__':
    """
    read adata object, compute all metrics and output csv.
    """
    
    import argparse

    parser = argparse.ArgumentParser(description='Compute all metrics')

    parser.add_argument('-a', '--uncorrected', required=True)
    parser.add_argument('-i', '--integrated', required=True)
    parser.add_argument('-o', '--output', required=True, help='output directory')
    parser.add_argument('-b', '--batch_key', required=True, help='Key of batch')
    parser.add_argument('-l', '--label_key', required=True, help='Key of annotated labels e.g. "cell_type"')
    parser.add_argument('-t', '--type', required=True, help='Type of result: full, embed, knn')
    parser.add_argument('-c', '--cluster_key', default='louvain', help='Name of cluster key, use it for new clustering if key is not present')
    parser.add_argument('-s', '--s_phase', default=None, help='S-phase marker genes')
    parser.add_argument('-g', '--g2m_phase', default=None, help='G2-/M-phase marker genes')
    parser.add_argument('-v', '--hvgs', default=None, help='Number of highly variable genes', type=int)
    args = parser.parse_args()
    
    import os
    
    result_types = [
        "full", # reconstructed expression data
        "embed", # embedded/latent space
        "knn" # only corrected neighbourhood graph as output
    ]
    if args.type not in result_types:
        raise ValueError(f'{args.type} is not a valid result type flag')
    
    batch_key = args.batch_key
    label_key = args.label_key
    cluster_key = args.cluster_key
    cc = (args.s_phase is not None) and (args.g2m_phase is not None)
    hvg = args.hvgs is not None
    
    ###
    
    print("reading files")
    adata = sc.read(args.uncorrected, cache=True)
    print("adata before integration")
    print(adata)
    adata_int = sc.read(args.integrated, cache=True)
    print("adata after integration")
    print(adata_int)
    
    # metric flags
    si_embed_before = si_embed_after = 'X_pca'
    neighbors = True
    pca = True
    pcr_ = True
    
    if (args.type == "embed"):
        si_embed_after = "embed"
        adata_int.obsm["embed"] = adata_int.obsm["X_pca"].copy()
        print(adata)
    elif (args.type == "knn"):
        hvg = False
        neighbors = False
        pca = False
        pcr_ = False
    
    print("reducing data")
    scIB.preprocessing.reduce_data(adata, batch_key=batch_key, umap=False,
                                   neighbors=neighbors, pca=pca,
                                   hvg=hvg, n_top_genes=args.hvgs)
    scIB.preprocessing.reduce_data(adata_int, batch_key=None, umap=False,
                                   neighbors=neighbors, pca=pca,
                                   hvg=hvg, n_top_genes=args.hvgs)
    
    print("clustering")
    for key, data in {'uncorrected':adata, 'integrated':adata_int}.items():
        res_max, nmi_max, nmi_all = scIB.cl.opt_louvain(data, 
                        label_key=label_key, cluster_key=cluster_key, 
                        plot=False, force=True, inplace=True)
        # save data for NMI profile plot
        nmi_all.to_csv(os.path.join(args.output, f'{key}_nmi.txt'))
    
    if cc:
        print("scoring cell cycle genes")
        s_genes = open(args.s_phase).read().split('\n')
        s_genes = [gene for gene in s_genes if gene in adata.var_names]
        g2m_genes = open(args.g2m_phase).read().split('\n')
        g2m_genes = [gene for gene in g2m_genes if gene in adata.var_names]
        if len(s_genes)+len(g2m_genes) == 0:
            print('no cell cycle genes in adata, skipping cell cycle effect')
            cc = False
        else:
            sc.tl.score_genes_cell_cycle(adata, s_genes, g2m_genes)
    
    print("computing metrics")
    results = scIB.me.metrics(adata, adata_int, hvg=hvg,
                    batch_key=batch_key, group_key=label_key, cluster_key=cluster_key,
                    silhouette_=True,  si_embed_pre=si_embed_before, si_embed_post=si_embed_after,
                    nmi_=True, ari_=True, nmi_method='max', nmi_dir=None,
                    pcr_=pcr_, kBET_=False, cell_cycle_=cc, verbose=False
            )
    # save metrics' results
    results.to_csv(os.path.join(args.output, 'metrics.tsv'))
    
    print("done")

