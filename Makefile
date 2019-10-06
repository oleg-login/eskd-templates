.PHONY: index spec

default: all

all: index spec

index:
	cd index && \
	cd Scripts/python/index/doc/ && \
	asciidoctor help.adoc && \
	cd - && \
	zip -FS -r ~/.config/libreoffice/4/user/template/Перечень\ элементов.ott * -x Scripts/python/index/doc/help.adoc

spec:
	cd spec && \
	cd Scripts/python/spec/doc/ && \
	asciidoctor help.adoc && \
	cd - && \
	zip -FS -r ~/.config/libreoffice/4/user/template/Спецификация.ott * -x Scripts/python/spec/doc/help.adoc