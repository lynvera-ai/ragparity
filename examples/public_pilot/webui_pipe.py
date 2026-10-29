"""
title: RAGParity public documents
version: 0.1.0
license: Apache-2.0
description: Local retrieval, evidence selection and explicit abstention for public documents.
"""

import sys

sys.path.insert(0, "/app/ragparity")

from chat_adapter import ChatAdapter  # noqa: E402


class Pipe(ChatAdapter):
    pass
