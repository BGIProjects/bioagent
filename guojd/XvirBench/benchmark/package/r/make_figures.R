#!/usr/bin/env Rscript
# Generate SCI-style figures from extracted TSVs. Missing tables/columns are skipped.
suppressPackageStartupMessages({
  library(ggplot2)
  library(dplyr)
  library(tidyr)
  library(readr)
  library(stringr)
  library(scales)
  library(patchwork)
  library(ggbeeswarm)
})

args <- commandArgs(trailingOnly = TRUE)
table_dir <- if (length(args) >= 1) args[[1]] else "tables"
fig_dir   <- if (length(args) >= 2) args[[2]] else "figures"

ca <- commandArgs(FALSE)
file_arg <- sub("^--file=", "", ca[grepl("^--file=", ca)])
script_dir <- if (length(file_arg)) dirname(normalizePath(file_arg[[1]])) else getwd()
theme_r <- file.path(script_dir, "00_sci_theme.R")
if (!file.exists(theme_r)) {
  cand <- file.path(dirname(fig_dir), "r", "00_sci_theme.R")
  if (file.exists(cand)) theme_r <- cand
}
if (!file.exists(theme_r)) stop("cannot find 00_sci_theme.R")
source(theme_r, local = FALSE)

dir.create(fig_dir, recursive = TRUE, showWarnings = FALSE)
master <- safe_read(file.path(table_dir, "master_sample_metrics.tsv"))
if (is.null(master)) quit(save = "no", status = 0)

if ("method" %in% names(master)) {
  master$method_lab <- label_method(master$method)
}
core <- master
if ("in_core_cohort" %in% names(master)) {
  core <- master %>% filter(in_core_cohort %in% c(TRUE, "True", "true", 1, "1"))
  if (nrow(core) == 0) core <- master
}

has_method <- "method_lab" %in% names(core) && n_distinct(na.omit(core$method_lab)) >= 2

color_method <- function(p) {
  if (has_method) {
    p + scale_colour_manual(values = setNames(unname(method_cols), method_labels), drop = FALSE, name = "Library method") +
      scale_fill_manual(values = setNames(unname(method_cols), method_labels), drop = FALSE, name = "Library method")
  } else {
    p + scale_colour_manual(values = c("all" = "#0072B2")) +
      scale_fill_manual(values = c("all" = "#0072B2"))
  }
}

jitter_box <- function(df, y, ylab, ypercent = FALSE) {
  d <- df %>% filter(!is.na(.data[[y]]))
  if (nrow(d) == 0) return(NULL)
  if (!has_method) d$method_lab <- factor("all")
  p <- ggplot(d, aes(x = method_lab, y = .data[[y]], colour = method_lab, fill = method_lab)) +
    geom_boxplot(width = 0.55, outlier.shape = NA, alpha = 0.25, linewidth = 0.35) +
    geom_quasirandom(width = 0.18, size = 1.4, alpha = 0.9) +
    labs(x = NULL, y = ylab) +
    theme_sci() +
    theme(axis.text.x = element_text(angle = 20, hjust = 1), legend.position = "none")
  if (ypercent) p <- p + scale_y_continuous(labels = percent_format(accuracy = 1))
  color_method(p)
}

# ---- Fig 01 coverage is drawn in Python (matrix). R: cohort overview ----
if (has_cols(core, c("sample_id"))) {
  d <- core
  d$depth <- if ("merge_r1_reads" %in% names(d)) d$merge_r1_reads / 1e6 else NA_real_
  if (!all(is.na(d$depth))) {
    if (!has_method) d$method_lab <- factor("all")
    p <- ggplot(d, aes(x = reorder(sample_id, depth), y = depth, fill = method_lab)) +
      geom_col(width = 0.75, colour = "black", linewidth = 0.2) +
      geom_hline(yintercept = 5, linetype = "dashed", linewidth = 0.3, colour = "#D55E00") +
      coord_flip() +
      labs(x = NULL, y = "Merged R1 reads (millions)", caption = "Dashed line: 5 million R1 reads low-depth flag") +
      theme_sci() +
      theme(legend.position = if (has_method) "bottom" else "none")
    if (has_method) {
      p <- p + scale_fill_manual(values = setNames(unname(method_cols), method_labels), name = NULL)
    } else {
      p <- p + scale_fill_manual(values = c("all" = "#0072B2"), guide = "none")
    }
    save_panel(p, file.path(fig_dir, "fig01_depth_by_sample"), width_mm = 114, height_mm = 90)
  }
}

# ---- W1 QC panels ----
if (has_cols(core, "read_retention_fastp_median")) {
  p <- jitter_box(core, "read_retention_fastp_median", "fastp read retention", ypercent = TRUE)
  if (!is.null(p)) save_panel(p, file.path(fig_dir, "fig02_w1_fastp_retention"), width_mm = 85, height_mm = 70)
}
if (has_cols(core, "q30_after_fastp_median")) {
  d <- core
  # q30 may be 0-1 or 0-100
  y <- d$q30_after_fastp_median
  if (isTRUE(max(y, na.rm = TRUE) <= 1.5)) d$q30_plot <- y else d$q30_plot <- y / 100
  p <- jitter_box(d, "q30_plot", "fastp Q30", ypercent = TRUE)
  if (!is.null(p)) save_panel(p, file.path(fig_dir, "fig03_w1_q30"), width_mm = 85, height_mm = 70)
}
if (has_cols(core, "rrna_retention_r1_median")) {
  d <- core
  y <- d$rrna_retention_r1_median
  if (isTRUE(max(y, na.rm = TRUE) <= 1.5)) d$rrna_plot <- y else d$rrna_plot <- y / 100
  p <- jitter_box(d, "rrna_plot", "R1 retained after rRNA depletion", ypercent = TRUE)
  if (!is.null(p)) save_panel(p, file.path(fig_dir, "fig04_w1_rrna_retention"), width_mm = 85, height_mm = 70)
}
if (has_cols(core, c("merge_r1_reads", "contigs_ge1kb_n"))) {
  d <- core %>% filter(!is.na(merge_r1_reads), !is.na(contigs_ge1kb_n))
  if (nrow(d) > 0) {
    if (!has_method) d$method_lab <- factor("all")
    p <- ggplot(d, aes(x = merge_r1_reads / 1e6, y = contigs_ge1kb_n, colour = method_lab)) +
      geom_point(size = 2.2, alpha = 0.9) +
      geom_text(aes(label = sample_id), size = 2, vjust = -0.8, show.legend = FALSE) +
      labs(x = "Merged R1 reads (millions)", y = "Contigs >=1 kb (n)") +
      theme_sci() +
      theme(legend.position = "bottom")
    p <- color_method(p)
    save_panel(p, file.path(fig_dir, "fig05_w1_depth_vs_contigs"), width_mm = 114, height_mm = 80)
  }
}

# ---- W2 ----
contigs <- safe_read(file.path(table_dir, "W2_contigs.tsv"))
if (has_cols(contigs, "checkv_quality")) {
  cq <- contigs %>%
    mutate(sample_id = if ("source_sample" %in% names(.)) source_sample else sample_id) %>%
    filter(!is.na(checkv_quality), checkv_quality != "") %>%
    count(sample_id, checkv_quality, name = "n")
  if ("method" %in% names(core)) {
    cq <- cq %>% left_join(core %>% select(sample_id, method_lab), by = "sample_id")
  }
  p <- ggplot(cq, aes(x = sample_id, y = n, fill = checkv_quality)) +
    geom_col(width = 0.8, colour = "black", linewidth = 0.15) +
    scale_fill_manual(values = okabe_ito, name = "CheckV") +
    labs(x = NULL, y = "Putative viral contigs (n)") +
    theme_sci() +
    theme(axis.text.x = element_text(angle = 45, hjust = 1), legend.position = "bottom")
  save_panel(p, file.path(fig_dir, "fig06_w2_checkv_by_sample"), width_mm = 114, height_mm = 80)
}
if (has_cols(contigs, "length")) {
  p <- ggplot(contigs, aes(x = length)) +
    geom_histogram(bins = 20, fill = "#0072B2", colour = "white", linewidth = 0.2) +
    scale_x_log10(labels = comma) +
    labs(x = "Putative viral contig length (bp, log10)", y = "Count") +
    theme_sci()
  save_panel(p, file.path(fig_dir, "fig07_w2_contig_length"), width_mm = 85, height_mm = 70)
}
if (has_cols(core, "n_putative_viral_contigs")) {
  p <- jitter_box(core, "n_putative_viral_contigs", "Putative viral contigs per sample (n)")
  if (!is.null(p)) save_panel(p, file.path(fig_dir, "fig08_w2_viral_contigs_by_method"), width_mm = 85, height_mm = 70)
}

# ---- W3 ----
host_top <- safe_read(file.path(table_dir, "W3_host_top_species.tsv"))
if (!is.null(host_top) && "inferred_mt_species" %in% names(host_top)) {
  ht <- host_top
  if ("source_sample" %in% names(ht) && !"sample_id" %in% names(ht)) ht$sample_id <- ht$source_sample
  # restrict to core if possible
  if ("sample_id" %in% names(core)) ht <- ht %>% filter(sample_id %in% core$sample_id)
  sp <- ht %>%
    count(inferred_mt_species, name = "n") %>%
    arrange(desc(n)) %>%
    slice_head(n = 12)
  p <- ggplot(sp, aes(x = reorder(inferred_mt_species, n), y = n)) +
    geom_col(fill = "#009E73", colour = "black", linewidth = 0.2, width = 0.75) +
    coord_flip() +
    labs(x = NULL, y = "Samples (n)", caption = "Top inferred mitochondrial species; not a clinical identification") +
    theme_sci()
  save_panel(p, file.path(fig_dir, "fig09_w3_host_species"), width_mm = 114, height_mm = 80)
}

# ---- W4 ----
if (has_cols(core, "kraken_unclassified_frac")) {
  d <- core
  y <- d$kraken_unclassified_frac
  if (isTRUE(max(y, na.rm = TRUE) > 1.5)) d$uncls <- y / 100 else d$uncls <- y
  p <- jitter_box(d, "uncls", "Kraken unclassified fraction", ypercent = TRUE)
  if (!is.null(p)) save_panel(p, file.path(fig_dir, "fig10_w4_unclassified"), width_mm = 85, height_mm = 70)
}
if (has_cols(core, "bracken_species_taxa")) {
  p <- jitter_box(core, "bracken_species_taxa", "Bracken species taxa (n)")
  if (!is.null(p)) save_panel(p, file.path(fig_dir, "fig11_w4_species_richness"), width_mm = 85, height_mm = 70)
}
top15 <- safe_read(file.path(table_dir, "W4_bracken_top15_species.tsv"))
if (!is.null(top15) && all(c("sample_id", "name", "fraction_total_reads") %in% names(top15))) {
  t15 <- top15 %>% filter(sample_id %in% core$sample_id)
  keep <- t15 %>%
    group_by(name) %>%
    summarise(tot = sum(fraction_total_reads, na.rm = TRUE), .groups = "drop") %>%
    arrange(desc(tot)) %>%
    slice_head(n = 10) %>%
    pull(name)
  t15 <- t15 %>%
    mutate(taxon = ifelse(name %in% keep, name, "Other (in top15 table)")) %>%
    group_by(sample_id, taxon) %>%
    summarise(frac = sum(fraction_total_reads, na.rm = TRUE), .groups = "drop")
  taxa <- unique(as.character(t15$taxon))
  pal <- setNames(okabe_ito[rep(seq_along(okabe_ito), length.out = length(taxa))], taxa)
  p <- ggplot(t15, aes(x = sample_id, y = frac, fill = taxon)) +
    geom_col(width = 0.85, colour = "black", linewidth = 0.1) +
    scale_y_continuous(labels = percent_format(accuracy = 1)) +
    scale_fill_manual(values = pal, name = NULL) +
    labs(x = NULL, y = "Bracken fraction of total reads",
         caption = "Top-15 species table only; fractions are among reported taxa, not the whole library") +
    theme_sci() +
    theme(axis.text.x = element_text(angle = 45, hjust = 1), legend.position = "bottom", legend.text = element_text(size = 6))
  save_panel(p, file.path(fig_dir, "fig12_w4_top_taxa"), width_mm = 174, height_mm = 95)
}

# ---- W5 ----
if (has_cols(core, "mapping_rate_pct")) {
  d <- core
  y <- d$mapping_rate_pct
  if (isTRUE(max(y, na.rm = TRUE) <= 1.5)) d$map_plot <- y else d$map_plot <- y / 100
  p <- jitter_box(d, "map_plot", "Reads mapped to viral contigs", ypercent = TRUE)
  if (!is.null(p)) save_panel(p, file.path(fig_dir, "fig13_w5_mapping_rate"), width_mm = 85, height_mm = 70)
}
if (has_cols(core, "max_rpm")) {
  d <- core %>% filter(!is.na(max_rpm))
  if (nrow(d) > 0) {
    if (!has_method) d$method_lab <- factor("all")
    p <- ggplot(d, aes(x = method_lab, y = max_rpm, colour = method_lab, fill = method_lab)) +
      geom_boxplot(width = 0.55, outlier.shape = NA, alpha = 0.25, linewidth = 0.35) +
      geom_quasirandom(width = 0.18, size = 1.4) +
      scale_y_log10(labels = comma) +
      labs(x = NULL, y = "Maximum viral RPM (log10)") +
      theme_sci() +
      theme(axis.text.x = element_text(angle = 20, hjust = 1), legend.position = "none")
    p <- color_method(p)
    save_panel(p, file.path(fig_dir, "fig14_w5_max_rpm"), width_mm = 85, height_mm = 70)
  }
}
if (has_cols(core, c("merge_r1_reads", "mapping_rate_pct"))) {
  d <- core %>% filter(!is.na(merge_r1_reads), !is.na(mapping_rate_pct))
  if (nrow(d) > 0) {
    if (!has_method) d$method_lab <- factor("all")
    y <- d$mapping_rate_pct
    d$map_plot <- if (isTRUE(max(y, na.rm = TRUE) <= 1.5)) y else y / 100
    p <- ggplot(d, aes(x = merge_r1_reads / 1e6, y = map_plot, colour = method_lab)) +
      geom_point(size = 2.2) +
      geom_text(aes(label = sample_id), size = 2, vjust = -0.8, show.legend = FALSE) +
      scale_y_continuous(labels = percent_format(accuracy = 0.01)) +
      labs(x = "Merged R1 reads (millions)", y = "Viral-contig mapping rate") +
      theme_sci() +
      theme(legend.position = "bottom")
    p <- color_method(p)
    save_panel(p, file.path(fig_dir, "fig15_w5_depth_vs_mapping"), width_mm = 114, height_mm = 80)
  }
}

message("figure generation finished")
