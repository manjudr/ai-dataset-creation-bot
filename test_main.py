import pytest
from io import StringIO
import sys

def test_simple_message():
    # Test to check if the simple message is printed correctly
    from main import print

    # Redirect stdout to capture print output
    captured_output = StringIO()
    sys.stdout = captured_output

    # Call the print function
    print("Hello, this is a test message!")

    # Reset stdout
    sys.stdout = sys.__stdout__

    # Assert the captured output
    assert captured_output.getvalue().strip() == "Hello, this is a test message!"