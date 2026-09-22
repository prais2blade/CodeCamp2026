import axios from "axios";

const API_URL = "http://127.0.0.1:8000/api/reports";

export const getReportSummary = async () => {

    const response = await axios.get(
        `${API_URL}/summary/`
    );

    return response.data;
};

export const getStudentStats = async () => {

    const response = await axios.get(
        `${API_URL}/student-stats/`
    );

    return response.data;
};

export const getAttendanceTrend = async () => {

    const response = await axios.get(
        `${API_URL}/trend/`
    );

    return response.data;
};