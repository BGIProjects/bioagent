# SCI / journal-style ggplot2 theme (Nature-like: classic axes, no grid, Okabe–Ito).
# Requires: ggplot2, scales, patchwork, ggbeeswarm, dplyr, readr, stringr, RColorBrewer

okabe_ito <- c(
  "#E69F00", "#56B4E9", "#009E73", "#F0E442",
  "#0072B2", "#D55E00", "#CC79A7", "#000000"
)

method_levels <- c("cDNA_Frag_30C5Min", "RNA_Frag_85C6Min", "RNA_Frag_94C7Min")
method_labels <- c("cDNA 30°C 5 min", "RNA 85°C 6 min", "RNA 94°C 7 min")
method_cols <- c(
  "cDNA_Frag_30C5Min" = "#E69F00",
  "RNA_Frag_85C6Min"  = "#0072B2",
  "RNA_Frag_94C7Min"  = "#009E73"
)

theme_sci <- function(base_size = 8, base_family = "sans") {
  ggplot2::theme_classic(base_size = base_size, base_family = base_family) +
    ggplot2::theme(
      line = ggplot2::element_line(colour = "black", linewidth = 0.35),
      axis.line = ggplot2::element_line(colour = "black", linewidth = 0.35),
      axis.ticks = ggplot2::element_line(colour = "black", linewidth = 0.35),
      axis.text = ggplot2::element_text(colour = "black", size = base_size),
      axis.title = ggplot2::element_text(colour = "black", size = base_size),
      legend.title = ggplot2::element_text(size = base_size),
      legend.text = ggplot2::element_text(size = base_size - 0.5),
      legend.key.size = grid::unit(0.35, "cm"),
      legend.background = ggplot2::element_blank(),
      legend.key = ggplot2::element_blank(),
      strip.background = ggplot2::element_blank(),
      strip.text = ggplot2::element_text(face = "bold", size = base_size),
      plot.title = ggplot2::element_text(size = base_size + 0.5, face = "bold", hjust = 0),
      plot.subtitle = ggplot2::element_text(size = base_size - 0.5, colour = "grey20"),
      plot.caption = ggplot2::element_text(size = base_size - 1, colour = "grey30", hjust = 0),
      plot.background = ggplot2::element_rect(fill = "white", colour = NA),
      panel.background = ggplot2::element_rect(fill = "white", colour = NA),
      panel.grid = ggplot2::element_blank(),
      plot.margin = ggplot2::margin(4, 6, 4, 4)
    )
}

save_panel <- function(plot, stem, width_mm = 85, height_mm = 70, dpi = 300) {
  png_path <- paste0(stem, ".png")
  pdf_path <- paste0(stem, ".pdf")
  ggplot2::ggsave(png_path, plot, width = width_mm, height = height_mm, units = "mm", dpi = dpi, bg = "white")
  ggplot2::ggsave(pdf_path, plot, width = width_mm, height = height_mm, units = "mm", bg = "white")
  message("wrote ", png_path)
}

safe_read <- function(path) {
  if (!file.exists(path)) return(NULL)
  df <- tryCatch(readr::read_tsv(path, show_col_types = FALSE), error = function(e) NULL)
  if (is.null(df) || nrow(df) == 0) return(NULL)
  df
}

has_cols <- function(df, cols) {
  !is.null(df) && all(cols %in% names(df))
}

label_method <- function(x) {
  factor(
    x,
    levels = method_levels,
    labels = method_labels
  )
}
