import streamlit as st
from agent import get_valid_result, explain_result, check_explanation, generate_chart

st.set_page_config(page_title="AI Analytics Agent", layout="wide")
st.title("AI Analytics Agent")
st.caption("Ask a question about the Superstore sales data in plain English.")

question = st.text_input(
    "Your question",
    placeholder="e.g. Which region has the lowest sales?"
)

if st.button("Ask") and question.strip():
    with st.spinner("Thinking..."):
        try:
            sql, result = get_valid_result(question)
        except Exception as e:
            st.error(f"Could not answer this question: {e}")
            st.stop()

        explanation = explain_result(question, sql, result)
        unverified = check_explanation(explanation, result)

    st.subheader("Answer")
    # Escape $ so Streamlit doesn't treat dollar amounts as math formatting
    st.write(explanation.replace("$", "\\$"))

    if unverified:
        st.warning(f"Some numbers in this explanation don't match the data: {unverified}")
    else:
        st.success("Number check passed: all figures match the query result.")

    fig = generate_chart(result, question)
    if fig is not None:
        st.plotly_chart(fig)

    with st.expander("SQL used"):
        st.code(sql, language="sql")

    with st.expander("Raw result"):
        st.dataframe(result)