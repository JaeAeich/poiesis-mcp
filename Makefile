# Docker image configuration
REGISTRY_NAMESPACE ?= jaeaeich
NAME := poiesis-mcp
VERSION := $(shell uv tree | grep ${NAME} | awk '{print $$2}' | sed 's/^v//')
BUILD_DATE := $(shell date -u +'%Y-%m-%dT%H:%M:%SZ')
GIT_REVISION := $(shell git rev-parse HEAD)
PY_VERSION := 3.13.0
DOCKERFILE := deployment/images/Dockerfile

# Full image names
IMAGE_NAME := ${REGISTRY_NAMESPACE}/${NAME}
IMAGE_TAG_LATEST := ${IMAGE_NAME}:latest
IMAGE_TAG_VERSION := ${IMAGE_NAME}:${VERSION}

.PHONY: format-lint fl
format-lint:
	@echo "\nRunning linter and formatter using ruff and typos +++++++++++++++++++++++++++++\n"
	@ruff format && ruff check --fix
fl: format-lint

.PHONY: install i
install:
	@echo "\nInstalling this package its dependencies ++++++++++++++++++++++++++++++++++++++\n"
	@uv sync --all-extras --all-groups
i: install

.PHONY: type-check tc
type-check:
	@echo "\nPerforming type checking with pyrefly ++++++++++++++++++++++++++++++++++++++++\n"
	@uv run pyrefly check poiesis_mcp
tc: type-check

.PHONY: precommit-check pc
precommit-check:
	@echo "\nRunning pre-commit checks +++++++++++++++++++++++++++++++++++++++++++++++++++++\n"
	@pre-commit run --all-files
pc: precommit-check

phony: build-docker-image bi
build-docker-image:
	@echo "\nbuilding docker image +++++++++++++++++++++++++++++++++++++++++++++++++++++++++\n"
	@docker build \
		--build-arg py_version="${py_version}" \
		--build-arg build_date="${build_date}" \
		--build-arg git_revision="${git_revision}" \
		--build-arg version="${version}" \
		-t jaeaeich/poiesis-mcp:latest \
		-f ${DOCKERFILE} .
	@echo "\ndocker image built successfully: jaeaeich/poiesis-mcp:latest\n"
bi: build-docker-image
