import apiClient from "./apiClient";

export const getStudentDetail = async (studentId) => {

    const response = await apiClient.get(
        `/students/${studentId}/`
    );

    return response.data;
};

export const getStudents = async () => {

    const response = await apiClient.get(
        "/students/"
    );

    return response.data;

};