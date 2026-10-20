# Usage: Rscript render.R <in.json> <out.sql> [circeR_lib]
# Builds cohort SQL with CirceR (generateStats = FALSE, like ATLAS "Export > SQL"),
# then resolves SqlRender {cond}?{...} blocks, leaving @parameters in place.
args <- commandArgs(trailingOnly = TRUE)
if (length(args) >= 3) .libPaths(c(args[3], .libPaths()))
suppressWarnings(suppressMessages({ library(CirceR); library(SqlRender) }))
json <- paste(readLines(args[1], warn = FALSE, encoding = "UTF-8"), collapse = "\n")
expr <- CirceR::cohortExpressionFromJson(json)
opts <- CirceR::createGenerateOptions(generateStats = FALSE)
sql  <- CirceR::buildCohortQuery(expr, opts)
sql  <- suppressWarnings(SqlRender::render(sql))
writeLines(sql, args[2], useBytes = TRUE)
cat("CirceR", as.character(packageVersion("CirceR")), "->", basename(args[2]), nchar(sql), "chars\n")
