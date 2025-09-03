# Pattern rule to convert .nld (natural language diagram) to .mmd (mermaid code)
%.mmd: %.nld
	# Replace this command with your LLM or script that converts natural language to mermaid code
	python nld_to_mermaid.py $< > $@

# Pattern rule to convert .mmd (mermaid code) to .svg (rendered image)
%.svg: %.mmd
	# Replace this command with your mermaid CLI or renderer command
	mermaid -i $< -o $@

# Optional: default target to build all .svg files from all .nld files in the directory
SVGS := $(patsubst %.nld,%.svg,$(wildcard *.nld))

all: $(SVGS)

